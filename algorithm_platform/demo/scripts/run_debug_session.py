import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
import shlex
from typing import Dict, List, Optional


running = True
child_process = None  # type: Optional[subprocess.Popen]


def stop_handler(signum, frame):
    del signum, frame
    global running
    running = False


def terminate_child() -> None:
    global child_process
    if child_process is None or child_process.poll() is not None:
        return
    try:
        os.killpg(child_process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    for _ in range(10):
        time.sleep(0.1)
        if child_process.poll() is not None:
            return
    try:
        os.killpg(child_process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def load_metadata(runtime_dir: Path) -> Dict[str, object]:
    metadata_path = runtime_dir / "current" / "metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_state(runtime_dir: Path, status: str, **extra: object) -> None:
    payload = {"status": status, **extra}
    (runtime_dir / "runner_state.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def normalize_entrypoint(entrypoint: str) -> List[str]:
    command = shlex.split(entrypoint)
    if not command:
        raise RuntimeError("entrypoint is empty")
    if command[0] in {"python", "python3"}:
        command[0] = sys.executable
    return command


def start_child(runtime_dir: Path, metadata: Dict[str, object]) -> subprocess.Popen:
    current_dir = runtime_dir / "current"
    code_dir = current_dir / "code"
    entrypoint = (metadata.get("entrypoint") or "").strip()
    if not entrypoint:
        raise RuntimeError("entrypoint is required in runtime metadata")
    if not code_dir.exists():
        raise RuntimeError(f"runtime code directory does not exist: {code_dir}")

    env = os.environ.copy()
    env["ALGORITHM_VERSION_UUID"] = metadata.get("versionUuid", "")
    env["ALGORITHM_VERSION"] = metadata.get("version", "")
    env["ALGORITHM_VERSION_NAME"] = metadata.get("versionName", "")
    runtime_config_path = metadata.get("runtimeConfigPath", "")
    if runtime_config_path:
        env["ALGORITHM_CONFIG_PATH"] = runtime_config_path
        env["APP_CONFIG_PATH"] = runtime_config_path

    return subprocess.Popen(
        normalize_entrypoint(entrypoint),
        cwd=str(code_dir),
        env=env,
        start_new_session=True,
    )


def main() -> int:
    if len(sys.argv) < 2:
        print("runtime dir is required", file=sys.stderr, flush=True)
        return 1

    runtime_dir = Path(sys.argv[1]).resolve()
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)

    metadata = load_metadata(runtime_dir)
    version_uuid = metadata.get("versionUuid", "unknown")
    version_name = metadata.get("versionName", "unknown")
    entrypoint = metadata.get("entrypoint", "")
    print(
        f"debug runner started pid={os.getpid()} runtime={runtime_dir} version={version_uuid} entrypoint={entrypoint}",
        flush=True,
    )
    write_state(runtime_dir, "STARTING", versionUuid=version_uuid, entrypoint=entrypoint)

    global child_process
    try:
        child_process = start_child(runtime_dir, metadata)
        write_state(
            runtime_dir,
            "RUNNING",
            versionUuid=version_uuid,
            entrypoint=entrypoint,
            childPid=child_process.pid,
        )
        print(
            f"started child pid={child_process.pid} version={version_uuid} name={version_name}",
            flush=True,
        )
        while running:
            exit_code = child_process.poll()
            if exit_code is not None:
                write_state(
                    runtime_dir,
                    "FAILED",
                    versionUuid=version_uuid,
                    entrypoint=entrypoint,
                    childPid=child_process.pid,
                    error=f"child exited with code {exit_code}",
                )
                print(
                    f"child exited pid={child_process.pid} code={exit_code} version={version_uuid}",
                    flush=True,
                )
                return exit_code
            time.sleep(0.5)
    except Exception as exc:
        write_state(runtime_dir, "FAILED", versionUuid=version_uuid, entrypoint=entrypoint, error=str(exc))
        print(f"debug runner failed: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        terminate_child()
        write_state(runtime_dir, "STOPPED", versionUuid=version_uuid, entrypoint=entrypoint)
        print(f"debug runner stopped pid={os.getpid()}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
