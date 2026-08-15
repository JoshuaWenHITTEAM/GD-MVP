from __future__ import annotations

import base64
import json
import os
import socket
import struct
import subprocess
import sys
import time
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

import requests


TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
FINAL_USED_ROOT = PROJECT_ROOT.parent.parent
DATA_ROOT = FINAL_USED_ROOT / "Anti-UAV-Tracking-V0" / "Anti-UAV-Tracking-V0"
GT_ROOT = FINAL_USED_ROOT / "Anti-UAV-Tracking-V0" / "Anti-UAV-Tracking-V0GT"
OUTPUT_DIR = TESTS_DIR / "outputs"

VIDEO_NAME = os.getenv("TRACK_TEST_VIDEO", "video01")
NUM_TRACK_FRAMES = max(20, int(os.getenv("TRACK_TEST_NUM_FRAMES", "20")))
POST_REPLACE_TRACK_FRAMES = max(10, int(os.getenv("TRACK_TEST_POST_REPLACE_FRAMES", "10")))
REQUEST_TIMEOUT = int(os.getenv("TRACK_TEST_TIMEOUT", "300"))
EXTERNAL_BASE_URL = os.getenv("TRACK_TEST_BASE_URL")
MANAGED_SERVICE = EXTERNAL_BASE_URL is None
URL_SERVER_HOST = os.getenv("TRACK_TEST_URL_HOST")


def reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return sock.getsockname()[1]


def detect_host_ip() -> str:
    if URL_SERVER_HOST:
        return URL_SERVER_HOST

    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    finally:
        probe.close()


def wait_http_ready(url: str, timeout: int = 120) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=5)
            if resp.ok:
                return
            last_error = f"status={resp.status_code}, body={resp.text}"
        except requests.RequestException as exc:
            last_error = repr(exc)
        time.sleep(1)
    raise RuntimeError(f"service did not become ready: {url}, last_error={last_error}")


@contextmanager
def run_service():
    if EXTERNAL_BASE_URL:
        wait_http_ready(f"{EXTERNAL_BASE_URL}/healthz")
        yield EXTERNAL_BASE_URL.rstrip("/")
        return

    port = reserve_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        f"{PROJECT_ROOT}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else str(PROJECT_ROOT)
    )
    env["WEIGHT_ROOT"] = str(PROJECT_ROOT / "models")

    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.server:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_http_ready(f"{base_url}/healthz")
        yield base_url
    except Exception as exc:
        process.terminate()
        try:
            stdout, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, _ = process.communicate(timeout=5)
        raise RuntimeError(f"uvicorn service failed or test errored. partial_log=\n{stdout}") from exc
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@contextmanager
def run_static_server(directory: Path):
    port = reserve_port()
    host_ip = detect_host_ip()

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            return

    handler = partial(QuietHandler, directory=str(directory))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), handler)
    try:
        import threading

        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        yield f"http://{host_ip}:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def ensure_dataset(video_name: str) -> tuple[Path, Path]:
    video_dir = DATA_ROOT / video_name
    gt_path = GT_ROOT / f"{video_name}_gt.txt"
    if not video_dir.is_dir():
        raise FileNotFoundError(f"video directory not found: {video_dir}")
    if not gt_path.is_file():
        raise FileNotFoundError(f"gt file not found: {gt_path}")
    return video_dir, gt_path


def load_gt_xyxy(gt_path: Path) -> list[list[int]]:
    gt = []
    for line in gt_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        x, y, w, h = [int(float(v)) for v in line.split()]
        gt.append([x, y, x + w, y + h])
    return gt


def load_sequence(video_name: str, num_track_frames: int) -> tuple[list[Path], list[list[int]]]:
    video_dir, gt_path = ensure_dataset(video_name)
    frames = sorted(video_dir.glob("*.jpg"))
    gt = load_gt_xyxy(gt_path)
    needed = num_track_frames + POST_REPLACE_TRACK_FRAMES + 2
    if len(frames) < needed:
        raise ValueError(f"{video_name} has only {len(frames)} frames, need at least {needed}")
    if len(gt) < needed:
        raise ValueError(f"{video_name} gt has only {len(gt)} rows, need at least {needed}")
    return frames, gt


def decode_image(encoded: str) -> bytes:
    return base64.b64decode(encoded)


def get_image_size(image_path: Path) -> tuple[int, int]:
    with image_path.open("rb") as handle:
        data = handle.read()

    if data[:2] != b"\xff\xd8":
        raise ValueError(f"unsupported image format for size parsing: {image_path}")

    offset = 2
    length = len(data)
    while offset + 9 < length:
        if data[offset] != 0xFF:
            offset += 1
            continue

        marker = data[offset + 1]
        offset += 2

        if marker in {0xD8, 0xD9}:
            continue

        if offset + 2 > length:
            break

        segment_length = struct.unpack(">H", data[offset : offset + 2])[0]
        if segment_length < 2 or offset + segment_length > length:
            break

        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            height, width = struct.unpack(">HH", data[offset + 3 : offset + 7])
            return width, height

        offset += segment_length

    raise ValueError(f"failed to parse jpeg size: {image_path}")


def bbox_iou(box_a: list[int], box_b: list[int]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter = inter_w * inter_h
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def assert_bbox_valid(bbox_xyxy: list[int], image_size: tuple[int, int]) -> None:
    width, height = image_size
    x1, y1, x2, y2 = bbox_xyxy
    assert 0 <= x1 < x2 <= width, f"invalid bbox x-range: {bbox_xyxy}, width={width}"
    assert 0 <= y1 < y2 <= height, f"invalid bbox y-range: {bbox_xyxy}, height={height}"


def save_bytes(filename: str, data: bytes) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / filename
    output_path.write_bytes(data)
    return output_path


def post_file(base_url: str, endpoint: str, image_path: Path, data: Optional[dict] = None):
    with image_path.open("rb") as handle:
        return requests.post(
            f"{base_url}{endpoint}",
            data=data or {},
            files={"image": (image_path.name, handle, "image/jpeg")},
            timeout=REQUEST_TIMEOUT,
        )


def post_url(base_url: str, endpoint: str, payload: dict):
    return requests.post(f"{base_url}{endpoint}", json=payload, timeout=REQUEST_TIMEOUT)


def reset_template(base_url: str) -> dict:
    resp = requests.post(f"{base_url}/template/reset", timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def summarize_ious(ious: list[float]) -> dict:
    return {
        "avg_iou": sum(ious) / len(ious),
        "min_iou": min(ious),
        "max_iou": max(ious),
    }


def run_file_flow(base_url: str, frames: list[Path], gt: list[list[int]]) -> dict:
    image_size = get_image_size(frames[0])
    init_bbox = gt[0]
    resp = post_file(
        base_url,
        "/template/set/file",
        frames[0],
        data={"x1": init_bbox[0], "y1": init_bbox[1], "x2": init_bbox[2], "y2": init_bbox[3]},
    )
    resp.raise_for_status()
    template_data = resp.json()
    save_bytes("file_template_set.jpg", decode_image(template_data["cached_template_base64"]))

    ious = []
    tracked_paths = []
    for idx in range(1, NUM_TRACK_FRAMES + 1):
        resp = post_file(base_url, "/track/file", frames[idx])
        resp.raise_for_status()
        data = resp.json()
        assert_bbox_valid(data["bbox_xyxy"], image_size)
        iou = bbox_iou(data["bbox_xyxy"], gt[idx])
        ious.append(iou)
        tracked_paths.append(
            str(save_bytes(f"file_track_{idx:02d}.jpg", decode_image(data["tracked_image_base64"])))
        )

    replace_bbox = gt[NUM_TRACK_FRAMES + 1]
    resp = post_file(
        base_url,
        "/template/replace/file",
        frames[NUM_TRACK_FRAMES + 1],
        data={
            "x1": replace_bbox[0],
            "y1": replace_bbox[1],
            "x2": replace_bbox[2],
            "y2": replace_bbox[3],
        },
    )
    resp.raise_for_status()
    replace_data = resp.json()
    save_bytes("file_template_replace.jpg", decode_image(replace_data["cached_template_base64"]))

    post_replace_ious = []
    post_replace_paths = []
    for offset in range(POST_REPLACE_TRACK_FRAMES):
        frame_idx = NUM_TRACK_FRAMES + 2 + offset
        resp = post_file(base_url, "/track/file", frames[frame_idx])
        resp.raise_for_status()
        post_replace = resp.json()
        assert_bbox_valid(post_replace["bbox_xyxy"], image_size)
        iou = bbox_iou(post_replace["bbox_xyxy"], gt[frame_idx])
        post_replace_ious.append(iou)
        post_replace_paths.append(
            str(
                save_bytes(
                    f"file_track_after_replace_{offset + 1:02d}.jpg",
                    decode_image(post_replace["tracked_image_base64"]),
                )
            )
        )

    return {
        "template_cache_version": template_data["cache_version"],
        "replace_cache_version": replace_data["cache_version"],
        "frame_count": NUM_TRACK_FRAMES,
        **summarize_ious(ious),
        "post_replace_frame_count": POST_REPLACE_TRACK_FRAMES,
        "post_replace_first_iou": post_replace_ious[0],
        "post_replace_last_iou": post_replace_ious[-1],
        "post_replace_summary": summarize_ious(post_replace_ious),
        "tracked_paths": tracked_paths,
        "post_replace_paths": post_replace_paths,
    }


def run_url_flow(base_url: str, frames: list[Path], gt: list[list[int]]) -> dict:
    image_size = get_image_size(frames[0])
    with run_static_server(frames[0].parent) as static_base:
        init_bbox = gt[0]
        resp = post_url(
            base_url,
            "/init/url",
            {"image_url": f"{static_base}/{frames[0].name}", "initial_bbox_xyxy": init_bbox},
        )
        resp.raise_for_status()
        init_data = resp.json()
        save_bytes("url_init_template.jpg", decode_image(init_data["cached_template_base64"]))

        ious = []
        tracked_paths = []
        for idx in range(1, NUM_TRACK_FRAMES + 1):
            resp = post_url(base_url, "/track/url", {"image_url": f"{static_base}/{frames[idx].name}"})
            resp.raise_for_status()
            data = resp.json()
            assert_bbox_valid(data["bbox_xyxy"], image_size)
            iou = bbox_iou(data["bbox_xyxy"], gt[idx])
            ious.append(iou)
            tracked_paths.append(
                str(save_bytes(f"url_track_{idx:02d}.jpg", decode_image(data["tracked_image_base64"])))
            )

        replace_bbox = gt[NUM_TRACK_FRAMES + 1]
        resp = post_url(
            base_url,
            "/template/replace/url",
            {
                "image_url": f"{static_base}/{frames[NUM_TRACK_FRAMES + 1].name}",
                "initial_bbox_xyxy": replace_bbox,
            },
        )
        resp.raise_for_status()
        replace_data = resp.json()
        save_bytes("url_template_replace.jpg", decode_image(replace_data["cached_template_base64"]))

        post_replace_ious = []
        post_replace_paths = []
        for offset in range(POST_REPLACE_TRACK_FRAMES):
            frame_idx = NUM_TRACK_FRAMES + 2 + offset
            resp = post_url(base_url, "/track/url", {"image_url": f"{static_base}/{frames[frame_idx].name}"})
            resp.raise_for_status()
            post_replace = resp.json()
            assert_bbox_valid(post_replace["bbox_xyxy"], image_size)
            iou = bbox_iou(post_replace["bbox_xyxy"], gt[frame_idx])
            post_replace_ious.append(iou)
            post_replace_paths.append(
                str(
                    save_bytes(
                        f"url_track_after_replace_{offset + 1:02d}.jpg",
                        decode_image(post_replace["tracked_image_base64"]),
                    )
                )
            )

    return {
        "template_cache_version": init_data["cache_version"],
        "replace_cache_version": replace_data["cache_version"],
        "frame_count": NUM_TRACK_FRAMES,
        **summarize_ious(ious),
        "post_replace_frame_count": POST_REPLACE_TRACK_FRAMES,
        "post_replace_first_iou": post_replace_ious[0],
        "post_replace_last_iou": post_replace_ious[-1],
        "post_replace_summary": summarize_ious(post_replace_ious),
        "tracked_paths": tracked_paths,
        "post_replace_paths": post_replace_paths,
    }


def main() -> None:
    frames, gt = load_sequence(VIDEO_NAME, NUM_TRACK_FRAMES)
    OUTPUT_DIR.mkdir(exist_ok=True)

    with run_service() as base_url:
        healthz = requests.get(f"{base_url}/healthz", timeout=10)
        ready = requests.get(f"{base_url}/ready", timeout=10)
        version = requests.get(f"{base_url}/version", timeout=10)
        version.raise_for_status()

        summary = {
            "video_name": VIDEO_NAME,
            "num_track_frames": NUM_TRACK_FRAMES,
            "post_replace_track_frames": POST_REPLACE_TRACK_FRAMES,
            "managed_service": MANAGED_SERVICE,
            "base_url": base_url,
            "healthz": {"status_code": healthz.status_code, "body": healthz.json()},
            "ready": {"status_code": ready.status_code, "body": ready.json() if ready.headers.get("content-type", "").startswith("application/json") else ready.text},
            "version": version.json(),
            "file_flow": run_file_flow(base_url, frames, gt),
            "reset_after_file_flow": reset_template(base_url),
            "url_flow": run_url_flow(base_url, frames, gt),
        }

    summary_path = OUTPUT_DIR / "track_siamrpnpp_test_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(summary_path)


if __name__ == "__main__":
    main()
