import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from db import BASE_DIR, fetch_one, now_iso, update_by_uuid


RUNTIME_ROOT = BASE_DIR / "runtime"
VERSION_SNAPSHOT_ROOT = RUNTIME_ROOT / "version_snapshots"
DEBUG_SESSION_ROOT = RUNTIME_ROOT / "debug_sessions"
HOT_UPDATE_SCRIPT = BASE_DIR / "scripts" / "hot_update_demo.sh"
DEBUG_RUNNER_SCRIPT = BASE_DIR / "scripts" / "run_debug_session.py"
MUTABLE_DEBUG_SESSION_STATUSES = {"RUNNING", "ROLLBACK"}


def runtime_path_for_session(session_uuid: str) -> Path:
    return DEBUG_SESSION_ROOT / session_uuid


def delete_session_runtime(session_uuid: str) -> None:
    shutil.rmtree(runtime_path_for_session(session_uuid), ignore_errors=True)


def update_debug_session(session_uuid: str, **values: Any) -> None:
    payload = dict(values)
    payload.setdefault("updatedAt", now_iso())
    update_by_uuid("debug_sessions", session_uuid, payload)


def update_hot_update(hot_update_uuid: str, **values: Any) -> None:
    update_by_uuid("hot_updates", hot_update_uuid, values)


def sync_session_state_file(session_uuid: str) -> None:
    session = fetch_one("SELECT * FROM debug_sessions WHERE uuid = ?", (session_uuid,))
    if not session:
        return

    write_json(
        runtime_path_for_session(session_uuid) / "session_state.json",
        {
            "uuid": session["uuid"],
            "algorithmUuid": session["algorithmUuid"],
            "baseVersionUuid": session["baseVersionUuid"],
            "currentVersionUuid": session["currentVersionUuid"],
            "debugStatus": session["debugStatus"],
            "processPid": session.get("processPid"),
            "runtimePath": session.get("runtimePath", ""),
            "lastError": session.get("lastError", ""),
            "updatedAt": session["updatedAt"],
        },
    )


def stop_debug_process(pid: int | None) -> None:
    if not pid or not process_is_alive(pid):
        return

    os.kill(pid, signal.SIGTERM)
    for _ in range(10):
        time.sleep(0.1)
        if not process_is_alive(pid):
            return
    os.kill(pid, signal.SIGKILL)


def provision_debug_session(session_uuid: str) -> None:
    time.sleep(0.6)
    session = require_debug_session(session_uuid)
    if not session or session["debugStatus"] != "PENDING":
        sync_session_state_file(session_uuid)
        return

    runtime_dir = runtime_path_for_session(session_uuid)
    try:
        version = require_version(session["currentVersionUuid"])
        if not version:
            raise RuntimeError("current version not found during debug session provisioning")

        prepare_runtime(runtime_dir, version)
        process_pid = start_debug_process(runtime_dir)
        update_debug_session(
            session_uuid,
            debugStatus="RUNNING",
            runtimePath=str(runtime_dir),
            processPid=process_pid,
            lastError="",
        )
    except Exception as exc:
        runtime_dir.mkdir(parents=True, exist_ok=True)
        append_log(runtime_dir / "logs" / "session.log", f"provision failed: {exc}")
        update_debug_session(
            session_uuid,
            debugStatus="FAILED",
            runtimePath=str(runtime_dir),
            processPid=None,
            lastError=str(exc),
        )
    finally:
        sync_session_state_file(session_uuid)


def run_hot_update_job(hot_update_uuid: str) -> None:
    hot_update = fetch_one("SELECT * FROM hot_updates WHERE uuid = ?", (hot_update_uuid,))
    if not hot_update:
        return

    session_uuid = hot_update["debugSessionUuid"]
    session = require_debug_session(session_uuid)
    if not session:
        update_hot_update(
            hot_update_uuid,
            updateStatus="FAILED",
            finishedAt=now_iso(),
            errorMessage="debug session not found",
            resultSummary="hot update aborted before execution",
        )
        return

    target_version = require_version(hot_update["toVersionUuid"])
    if not target_version:
        update_hot_update(
            hot_update_uuid,
            updateStatus="FAILED",
            finishedAt=now_iso(),
            errorMessage="target version not found",
            resultSummary="hot update aborted before execution",
        )
        update_debug_session(session_uuid, debugStatus="FAILED", lastError="target version not found")
        sync_session_state_file(session_uuid)
        return

    runtime_dir = runtime_path_for_session(session_uuid)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    update_hot_update(hot_update_uuid, updateStatus="RUNNING")
    update_debug_session(session_uuid, debugStatus="RUNNING", lastError="")
    sync_session_state_file(session_uuid)

    stdout = ""
    stderr = ""
    try:
        time.sleep(0.6)
        snapshot_dir = ensure_version_snapshot(target_version)
        result = subprocess.run(
            [
                "bash",
                str(HOT_UPDATE_SCRIPT),
                str(runtime_dir),
                hot_update["fromVersionUuid"],
                hot_update["toVersionUuid"],
                str(snapshot_dir),
            ],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = result.stdout
        stderr = result.stderr
        action_log_path = write_hot_update_log(session_uuid, hot_update_uuid, stdout, stderr)
        if result.returncode != 0:
            raise RuntimeError(
                stderr.strip() or stdout.strip() or "hot update script exited with non-zero status"
            )

        process_pid = restart_debug_process(runtime_dir, session.get("processPid"))
        update_debug_session(
            session_uuid,
            currentVersionUuid=hot_update["toVersionUuid"],
            debugStatus="RUNNING",
            processPid=process_pid,
            lastError="",
        )
        update_hot_update(
            hot_update_uuid,
            updateStatus="SUCCESS",
            finishedAt=now_iso(),
            errorMessage="",
            resultSummary=f"switched to {target_version['version']} and restarted pid {process_pid}",
            actionLogPath=action_log_path,
        )
    except Exception as exc:
        action_log_path = write_hot_update_log(session_uuid, hot_update_uuid, stdout, stderr)
        rollback_message = str(exc)
        if restore_runtime(runtime_dir):
            process_pid = restart_debug_process(runtime_dir, session.get("processPid"))
            update_debug_session(
                session_uuid,
                currentVersionUuid=hot_update["fromVersionUuid"],
                debugStatus="ROLLBACK",
                processPid=process_pid,
                lastError=rollback_message,
            )
            update_hot_update(
                hot_update_uuid,
                updateStatus="ROLLBACK",
                finishedAt=now_iso(),
                errorMessage=rollback_message,
                resultSummary="hot update failed and rollback completed",
                actionLogPath=action_log_path,
            )
        else:
            stop_debug_process(session.get("processPid"))
            update_debug_session(
                session_uuid,
                debugStatus="FAILED",
                processPid=None,
                lastError=rollback_message,
            )
            update_hot_update(
                hot_update_uuid,
                updateStatus="FAILED",
                finishedAt=now_iso(),
                errorMessage=rollback_message,
                resultSummary="hot update failed and rollback could not be completed",
                actionLogPath=action_log_path,
            )
    finally:
        sync_session_state_file(session_uuid)


def require_debug_session(session_uuid: str) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM debug_sessions WHERE uuid = ?", (session_uuid,))


def require_version(version_uuid: str) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM versions WHERE uuid = ?", (version_uuid,))


def ensure_version_snapshot(version: dict[str, Any]) -> Path:
    snapshot_dir = VERSION_SNAPSHOT_ROOT / version["uuid"]
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        snapshot_dir / "metadata.json",
        {
            "versionUuid": version["uuid"],
            "version": version["version"],
            "versionName": version["versionName"],
            "entrypoint": version["entrypoint"],
            "configPath": version["configPath"],
            "publishStatus": version["publishStatus"],
            "generatedAt": now_iso(),
        },
    )
    (snapshot_dir / "main.py").write_text(
        "\n".join(
            [
                f'VERSION_UUID = "{version["uuid"]}"',
                f'VERSION = "{version["version"]}"',
                f'VERSION_NAME = "{version["versionName"]}"',
                "",
                "def run() -> str:",
                '    return f"debug session is running {VERSION} ({VERSION_NAME})"',
                "",
                'if __name__ == "__main__":',
                "    print(run())",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return snapshot_dir


def prepare_runtime(runtime_dir: Path, version: dict[str, Any]) -> None:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
    replace_directory(ensure_version_snapshot(version), runtime_dir / "current")


def restore_runtime(runtime_dir: Path) -> bool:
    backup_dir = runtime_dir / "current_backup"
    if not backup_dir.exists():
        return False
    replace_directory(backup_dir, runtime_dir / "current")
    return True


def restart_debug_process(runtime_dir: Path, current_pid: int | None) -> int:
    stop_debug_process(current_pid)
    return start_debug_process(runtime_dir)


def start_debug_process(runtime_dir: Path) -> int:
    log_path = runtime_dir / "logs" / "debug-process.log"
    with log_path.open("ab") as handle:
        process = subprocess.Popen(
            [sys.executable, str(DEBUG_RUNNER_SCRIPT), str(runtime_dir)],
            cwd=str(runtime_dir),
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return process.pid


def process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def replace_directory(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def write_hot_update_log(
    session_uuid: str,
    hot_update_uuid: str,
    stdout: str,
    stderr: str,
) -> str:
    log_path = runtime_path_for_session(session_uuid) / "logs" / f"hot-update-{hot_update_uuid}.log"
    append_log(log_path, "stdout:")
    if stdout.strip():
        append_log(log_path, stdout.strip())
    append_log(log_path, "stderr:")
    if stderr.strip():
        append_log(log_path, stderr.strip())
    return str(log_path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{now_iso()}] {message}\n")
