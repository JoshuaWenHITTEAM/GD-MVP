import os
import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional


AGENTS_ROOT = Path(__file__).resolve().parents[2]
CONDA = os.environ.get("CONDA_EXE", "conda")
OUTPUT_ROOT = Path(__file__).resolve().parent / "smoke_outputs"


def http_get(url: str):
    with urllib.request.urlopen(url, timeout=20) as resp:
        return resp.read().decode("utf-8"), resp.status


def http_post(url: str, payload: dict):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8"), resp.status


def wait_for_server(base_url: str, timeout: int = 30, reporter=None) -> None:
    start = time.time()
    attempt = 0
    while time.time() - start < timeout:
        attempt += 1
        try:
            _, status = http_get(f"{base_url}/api/health")
            if status == 200:
                if reporter is not None:
                    reporter(f"服务已就绪: {base_url}/api/health")
                return
        except Exception:
            if reporter is not None:
                reporter(f"等待服务启动... 第 {attempt} 次检查")
            time.sleep(1)
    raise TimeoutError(f"Server did not become ready within {timeout} seconds")


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def iter_sse(url: str, max_events: Optional[int], timeout: int):
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        event_name = None
        data_lines = []
        seen = 0
        for raw_line in resp:
            line = raw_line.decode("utf-8").rstrip("\n")
            if not line:
                if event_name:
                    payload = "\n".join(data_lines)
                    yield event_name, payload
                    seen += 1
                    if max_events is not None and seen >= max_events:
                        return
                event_name = None
                data_lines = []
                continue
            if line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: "):
                data_lines.append(line[6:])


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def open_output_files():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_ROOT / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = output_dir / "transcript.log"
    server_log_path = output_dir / "server.log"
    transcript_fp = transcript_path.open("w", encoding="utf-8")
    return transcript_path, server_log_path, transcript_fp


def emit(line: str, transcript_fp) -> None:
    text = f"[{timestamp()}] {line}"
    print(text, flush=True)
    transcript_fp.write(text + "\n")
    transcript_fp.flush()


def emit_section(title: str, transcript_fp) -> None:
    emit("", transcript_fp)
    emit(f"=== {title} ===", transcript_fp)


def emit_response(label: str, status: int, body: str, transcript_fp) -> None:
    emit_section(label, transcript_fp)
    emit(f"HTTP {status}", transcript_fp)
    try:
        parsed = json.loads(body)
        formatted = json.dumps(parsed, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        formatted = body
    for line in formatted.splitlines():
        emit(line, transcript_fp)


def compact_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(", ", ": "))


def summarize_stream_event(event_name: str, payload_text: str) -> Optional[str]:
    try:
        envelope = json.loads(payload_text)
    except json.JSONDecodeError:
        return payload_text

    payload = envelope.get("payload", {})

    if event_name == "status":
        parts = [f"status={payload.get('status')}"]
        if payload.get("run_dir"):
            parts.append(f"run_dir={payload['run_dir']}")
        if payload.get("pid"):
            parts.append(f"pid={payload['pid']}")
        return ", ".join(parts)

    if event_name == "progress":
        current_step = payload.get("current_step")
        total_steps = payload.get("total_steps")
        progress = payload.get("progress")
        cpu_util = payload.get("cpu_util")
        gpu_util = payload.get("gpu_util")
        gpu_mem = payload.get("gpu_mem")
        if not current_step and not progress and cpu_util is None and gpu_util is None and gpu_mem is None:
            return None
        parts = []
        if current_step is not None and total_steps:
            percent = f"{float(progress) * 100:.1f}%" if progress is not None else "?"
            parts.append(f"step={current_step}/{total_steps}")
            parts.append(f"progress={percent}")
        if cpu_util is not None:
            parts.append(f"cpu={cpu_util}%")
        if gpu_util is not None:
            parts.append(f"gpu={gpu_util}%")
        if gpu_mem is not None:
            parts.append(f"gpu_mem={gpu_mem}MB")
        return ", ".join(parts) if parts else None

    if event_name == "metrics":
        step = payload.get("step")
        reward = payload.get("reward")
        td_loss = payload.get("td_loss")
        epsilon = payload.get("epsilon")
        learning_rate = payload.get("learning_rate")
        if step in (None, 0) and reward is None and td_loss is None and epsilon is None and learning_rate is None:
            return None
        parts = []
        if step is not None:
            parts.append(f"step={step}")
        if reward is not None:
            parts.append(f"reward={reward}")
        if td_loss is not None:
            parts.append(f"td_loss={td_loss}")
        if epsilon is not None:
            parts.append(f"epsilon={epsilon}")
        if learning_rate is not None:
            parts.append(f"lr={learning_rate}")
        return ", ".join(parts) if parts else compact_json(payload)

    if event_name == "log":
        message = payload.get("message")
        level = payload.get("level")
        if not message:
            return None
        return f"{level}: {message}" if level else str(message)

    if event_name == "checkpoint":
        parts = []
        if payload.get("global_step") is not None:
            parts.append(f"step={payload['global_step']}")
        if payload.get("checkpoint_path"):
            parts.append(f"checkpoint={payload['checkpoint_path']}")
        return ", ".join(parts) if parts else compact_json(payload)

    if event_name in {"completed", "failed"}:
        return compact_json(payload)

    return compact_json(envelope)


def main():
    parser = argparse.ArgumentParser(description="Smoke test training console backend")
    parser.add_argument("--base-url", default="http://127.0.0.1:30000", help="Existing backend base url, e.g. http://127.0.0.1:8000")
    parser.add_argument("--start-server", action="store_true", help="Start uvicorn automatically for the smoke test")
    parser.add_argument("--task-type", default="detect", choices=["detect", "track", "preprocess"])
    parser.add_argument("--port", type=int, default=30000)
    parser.add_argument("--stream-events", type=int, default=None)
    parser.add_argument("--server-wait-timeout", type=int, default=30)
    args = parser.parse_args()

    server_proc = None
    base_url = args.base_url
    transcript_path, server_log_path, transcript_fp = open_output_files()

    try:
        emit(f"演示记录文件: {transcript_path}", transcript_fp)
        if args.start_server:
            port = args.port or find_free_port()
            base_url = f"http://127.0.0.1:{port}"
            cmd = [
                CONDA,
                "run",
                "--no-capture-output",
                "-n",
                "CVRL",
                "uvicorn",
                "training_console_backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ]
            emit_section("启动服务", transcript_fp)
            emit(f"base_url = {base_url}", transcript_fp)
            emit(f"server_log = {server_log_path}", transcript_fp)
            server_log_fp = server_log_path.open("w", encoding="utf-8")
            server_proc = subprocess.Popen(
                cmd,
                cwd=str(AGENTS_ROOT),
                stdout=server_log_fp,
                stderr=subprocess.STDOUT,
            )
            wait_for_server(base_url, timeout=args.server_wait_timeout, reporter=lambda message: emit(message, transcript_fp))
        elif not base_url:
            raise SystemExit("Either provide --base-url or use --start-server")

        emit_section("接口 1: 健康检查 GET /api/health", transcript_fp)
        health_body, health_status = http_get(f"{base_url}/api/health")
        emit_response("health", health_status, health_body, transcript_fp)

        create_payload = {
            "task_type": args.task_type,
            "train_config": {
                "exp_name": f"smoke_{args.task_type}",
                "total_timesteps": 30,
                "learning_starts": 1,
                "train_frequency": 5,
                "save_checkpoints_freq": 10,
            },
        }
        emit_section("接口 2: 创建训练任务 POST /api/train/jobs", transcript_fp)
        emit(f"request = {json.dumps(create_payload, ensure_ascii=False)}", transcript_fp)
        create_body, create_status = http_post(f"{base_url}/api/train/jobs", create_payload)
        create_json = json.loads(create_body)
        job_id = create_json["job_id"]
        emit_response("create_job", create_status, create_body, transcript_fp)

        emit_section("接口 3: 查询任务详情 GET /api/train/jobs/{job_id}", transcript_fp)
        detail_body, detail_status = http_get(f"{base_url}/api/train/jobs/{job_id}")
        emit_response("job_detail", detail_status, detail_body, transcript_fp)

        emit_section("接口 4: 再次查询任务详情 GET /api/train/jobs/{job_id}", transcript_fp)
        final_detail, final_status = http_get(f"{base_url}/api/train/jobs/{job_id}")
        emit_response("final_job_detail", final_status, final_detail, transcript_fp)

        emit_section("接口 5: 最后订阅事件流 GET /api/train/jobs/{job_id}/stream", transcript_fp)
        if args.stream_events is None:
            emit("事件数不设上限；会持续输出直到 completed 或 failed", transcript_fp)
        else:
            emit(f"最多展示 {args.stream_events} 个事件；会持续输出直到 completed、failed 或达到上限", transcript_fp)
        last_summary = None
        for index, (event_name, payload) in enumerate(
            iter_sse(f"{base_url}/api/train/jobs/{job_id}/stream", args.stream_events, timeout=90),
            start=1,
        ):
            summary = summarize_stream_event(event_name, payload)
            if not summary:
                continue
            summary_key = f"{event_name}: {summary}"
            if summary_key == last_summary:
                continue
            emit(f"SSE #{index} {summary_key}", transcript_fp)
            last_summary = summary_key
            if event_name in {"completed", "failed"}:
                break
        emit(f"演示完成，完整记录见: {transcript_path}", transcript_fp)
    finally:
        if server_proc is not None:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_proc.kill()
        transcript_fp.close()


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(f"HTTPError: {exc.code} {exc.reason}", file=sys.stderr)
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        raise
