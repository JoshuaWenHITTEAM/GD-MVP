import asyncio
import os
import signal
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency
    psutil = None

from .config import (
    AGENTS_ROOT,
    ALLOWED_OVERRIDE_KEYS,
    CONDA_ENV_NAME,
    CONDA_RUNNER,
    JOBS_ROOT,
    TASK_DEFAULT_CONFIGS,
)
from .event_bus import EventBus
from .job_store import JobStore
from .utils import load_yaml, now_iso, parse_structured_log_line, save_yaml


class JobManager:
    def __init__(self, store: JobStore, event_bus: EventBus):
        self.store = store
        self.event_bus = event_bus
        self.jobs: Dict[str, dict] = {item["job_id"]: item for item in store.list()}
        self.processes: Dict[str, asyncio.subprocess.Process] = {}
        self.monitor_tasks: Dict[str, asyncio.Task] = {}
        JOBS_ROOT.mkdir(parents=True, exist_ok=True)

    def list_jobs(self) -> list[dict]:
        return sorted(self.jobs.values(), key=lambda item: item["created_at"], reverse=True)

    def get_job(self, job_id: str) -> Optional[dict]:
        return self.jobs.get(job_id)

    def _persist(self, job: dict) -> None:
        self.jobs[job["job_id"]] = job
        self.store.upsert(job)

    def _load_task_default(self, task_type: str) -> Dict[str, Any]:
        if task_type not in TASK_DEFAULT_CONFIGS:
            raise ValueError(f"Unsupported task_type: {task_type}")
        return load_yaml(TASK_DEFAULT_CONFIGS[task_type])

    def _merge_config(self, task_type: str, train_config: Dict[str, Any]) -> Dict[str, Any]:
        merged = deepcopy(self._load_task_default(task_type))
        unknown = [key for key in train_config if key not in ALLOWED_OVERRIDE_KEYS]
        if unknown:
            raise ValueError(f"Unsupported config keys: {', '.join(sorted(unknown))}")
        for key, value in train_config.items():
            if key in merged:
                merged[key] = value
        return merged

    async def create_job(self, task_type: str, train_config: Dict[str, Any]) -> dict:
        final_config = self._merge_config(task_type, train_config)
        job_id = f"job_{uuid4().hex[:12]}"
        created_at = now_iso()
        job_dir = JOBS_ROOT / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        merged_config_path = job_dir / "merged_config.yaml"
        save_yaml(merged_config_path, final_config)

        job = {
            "job_id": job_id,
            "task_type": task_type,
            "status": "queued",
            "created_at": created_at,
            "started_at": None,
            "ended_at": None,
            "progress": {
                "current_step": 0,
                "total_steps": int(final_config.get("total_timesteps", 0)),
                "progress": 0.0,
                "gpu_util": None,
                "gpu_mem": None,
                "cpu_util": None,
            },
            "summary": {
                "latest_reward": None,
                "latest_td_loss": None,
                "latest_lr": float(final_config.get("learning_rate")) if final_config.get("learning_rate") is not None else None,
                "latest_epsilon": None,
                "latest_checkpoint": None,
                "sps": None,
            },
            "runtime": {
                "pid": None,
                "run_dir": None,
                "log_file": None,
                "merged_config_path": str(merged_config_path),
            },
            "config": final_config,
            "error_message": None,
        }
        self._persist(job)
        await self._publish(job_id, "status", {"status": "queued"})
        asyncio.create_task(self._run_job(job_id))
        return job

    async def stop_job(self, job_id: str) -> dict:
        job = self.get_job(job_id)
        if not job:
            raise KeyError(job_id)
        process = self.processes.get(job_id)
        if process and process.returncode is None:
            process.send_signal(signal.SIGTERM)
            job["status"] = "stopped"
            job["ended_at"] = now_iso()
            self._persist(job)
            await self._publish(job_id, "status", {"status": "stopped"})
            await self._publish(job_id, "stopped", {"status": "stopped"})
        return job

    async def _run_job(self, job_id: str) -> None:
        job = self.jobs[job_id]
        job["status"] = "starting"
        job["started_at"] = now_iso()
        self._persist(job)
        await self._publish(job_id, "status", {"status": "starting"})

        config_path = job["runtime"]["merged_config_path"]
        cmd = [
            str(CONDA_RUNNER),
            "run",
            "--no-capture-output",
            "-n",
            CONDA_ENV_NAME,
            "python",
            str(AGENTS_ROOT / "DQNv2" / "dqn_main.py"),
            "train",
            "--config",
            config_path,
        ]
        env = os.environ.copy()
        env["MPLCONFIGDIR"] = env.get("MPLCONFIGDIR", "/tmp/mpl")
        env["PYTHONUNBUFFERED"] = "1"

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(AGENTS_ROOT),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self.processes[job_id] = process
        job["runtime"]["pid"] = process.pid
        job["status"] = "running"
        self._persist(job)
        await self._publish(job_id, "status", {"status": "running", "pid": process.pid})

        self.monitor_tasks[job_id] = asyncio.create_task(self._resource_monitor(job_id))

        assert process.stdout is not None
        async for raw_line in process.stdout:
            line = raw_line.decode("utf-8", errors="replace").rstrip()
            await self._handle_output_line(job_id, line)

        return_code = await process.wait()
        monitor_task = self.monitor_tasks.pop(job_id, None)
        if monitor_task:
            monitor_task.cancel()

        if job["status"] == "stopped":
            pass
        elif return_code == 0:
            job["status"] = "completed"
            await self._publish(job_id, "completed", {"status": "completed"})
        else:
            job["status"] = "failed"
            job["error_message"] = f"Training process exited with code {return_code}"
            await self._publish(job_id, "failed", {"status": "failed", "message": job["error_message"]})
        job["ended_at"] = now_iso()
        self._persist(job)
        self.processes.pop(job_id, None)

    async def _handle_output_line(self, job_id: str, line: str) -> None:
        job = self.jobs[job_id]
        await self._publish(
            job_id,
            "log",
            {
                "level": self._guess_log_level(line),
                "message": line,
            },
        )

        event_name, payload = parse_structured_log_line(line)
        if not event_name or payload is None:
            return

        if event_name == "TRAIN_RUN":
            job["runtime"]["run_dir"] = payload.get("run_dir")
            job["runtime"]["log_file"] = payload.get("log_file")
            self._persist(job)
            await self._publish(job_id, "status", {"status": job["status"], "run_dir": job["runtime"]["run_dir"]})
            return

        if event_name == "TRAIN_PROGRESS":
            current_step = int(payload.get("global_step", 0))
            total_steps = int(payload.get("total_timesteps", job["progress"]["total_steps"]))
            progress = float(payload.get("progress", 0.0))
            job["progress"]["current_step"] = current_step
            job["progress"]["total_steps"] = total_steps
            job["progress"]["progress"] = progress
            if payload.get("epsilon") is not None:
                job["summary"]["latest_epsilon"] = float(payload["epsilon"])
            if payload.get("learning_rate") is not None:
                job["summary"]["latest_lr"] = float(payload["learning_rate"])
            self._persist(job)
            await self._publish(
                job_id,
                "progress",
                {
                    "current_step": job["progress"]["current_step"],
                    "total_steps": job["progress"]["total_steps"],
                    "progress": job["progress"]["progress"],
                    "gpu_util": job["progress"]["gpu_util"],
                    "gpu_mem": job["progress"]["gpu_mem"],
                    "cpu_util": job["progress"]["cpu_util"],
                },
            )
            return

        if event_name == "TRAIN_METRICS":
            if payload.get("reward") is not None:
                job["summary"]["latest_reward"] = float(payload["reward"])
            if payload.get("epsilon") is not None:
                job["summary"]["latest_epsilon"] = float(payload["epsilon"])
            if payload.get("learning_rate") is not None:
                job["summary"]["latest_lr"] = float(payload["learning_rate"])
            self._persist(job)
            await self._publish(
                job_id,
                "metrics",
                {
                    "metric_source": "reward",
                    "step": int(payload.get("global_step", 0)),
                    "reward": payload.get("reward"),
                    "reward_total": payload.get("reward_total"),
                    "td_loss": None,
                    "epsilon": job["summary"]["latest_epsilon"],
                    "learning_rate": job["summary"]["latest_lr"],
                },
            )
            return

        if event_name == "TRAIN_MONITOR":
            if payload.get("td_loss") is not None:
                job["summary"]["latest_td_loss"] = float(payload["td_loss"])
            if payload.get("epsilon") is not None:
                job["summary"]["latest_epsilon"] = float(payload["epsilon"])
            if payload.get("learning_rate") is not None:
                job["summary"]["latest_lr"] = float(payload["learning_rate"])
            if payload.get("sps") is not None:
                job["summary"]["sps"] = int(payload["sps"])
            self._persist(job)
            await self._publish(
                job_id,
                "metrics",
                {
                    "metric_source": "monitor",
                    "step": int(payload.get("global_step", 0)),
                    "reward": None,
                    "td_loss": job["summary"]["latest_td_loss"],
                    "epsilon": job["summary"]["latest_epsilon"],
                    "learning_rate": job["summary"]["latest_lr"],
                    "sps": job["summary"]["sps"],
                },
            )
            return

        if event_name == "TRAIN_CHECKPOINT":
            job["summary"]["latest_checkpoint"] = payload.get("checkpoint_path")
            self._persist(job)
            await self._publish(job_id, "checkpoint", payload)

    async def _resource_monitor(self, job_id: str) -> None:
        while True:
            await asyncio.sleep(1.0)
            job = self.jobs.get(job_id)
            process = self.processes.get(job_id)
            if not job or not process or process.returncode is not None:
                return
            cpu_util = self._read_cpu_util()
            gpu_util, gpu_mem = await self._read_gpu_util()
            job["progress"]["cpu_util"] = cpu_util
            job["progress"]["gpu_util"] = gpu_util
            job["progress"]["gpu_mem"] = gpu_mem
            self._persist(job)
            await self._publish(
                job_id,
                "progress",
                {
                    "current_step": job["progress"]["current_step"],
                    "total_steps": job["progress"]["total_steps"],
                    "progress": job["progress"]["progress"],
                    "gpu_util": gpu_util,
                    "gpu_mem": gpu_mem,
                    "cpu_util": cpu_util,
                },
            )

    def _read_cpu_util(self) -> Optional[float]:
        if psutil is None:
            return None
        return float(psutil.cpu_percent(interval=None))

    async def _read_gpu_util(self) -> tuple[Optional[float], Optional[float]]:
        cmd = [
            "nvidia-smi",
            "--query-gpu=utilization.gpu,memory.used",
            "--format=csv,noheader,nounits",
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await process.communicate()
        except FileNotFoundError:
            return None, None

        if process.returncode != 0:
            return None, None
        first_line = stdout.decode("utf-8", errors="replace").strip().splitlines()
        if not first_line:
            return None, None
        try:
            util_str, mem_str = [item.strip() for item in first_line[0].split(",")[:2]]
            return float(util_str), float(mem_str)
        except (ValueError, IndexError):
            return None, None

    async def _publish(self, job_id: str, event_name: str, payload: Dict[str, Any]) -> None:
        await self.event_bus.publish(
            job_id,
            {
                "event": event_name,
                "job_id": job_id,
                "timestamp": now_iso(),
                "payload": payload,
            },
        )

    @staticmethod
    def _guess_log_level(line: str) -> str:
        for level in ("ERROR", "WARNING", "INFO", "DEBUG"):
            if f"| {level}" in line:
                return level
        return "INFO"
