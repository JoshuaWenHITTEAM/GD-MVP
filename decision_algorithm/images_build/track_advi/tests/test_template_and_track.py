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
from typing import Optional, Union

import requests


TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
FINAL_USED_ROOT = PROJECT_ROOT.parent.parent
DATA_ROOT = FINAL_USED_ROOT / "Anti-UAV-Tracking-V0" / "Anti-UAV-Tracking-V0"
GT_ROOT = FINAL_USED_ROOT / "Anti-UAV-Tracking-V0" / "Anti-UAV-Tracking-V0GT"
OUTPUT_DIR = TESTS_DIR / "outputs"

VIDEO_NAME = os.getenv("TRACK_TEST_VIDEO", "video01")
NUM_TRACK_FRAMES = max(20, int(os.getenv("TRACK_TEST_NUM_FRAMES", "20")))
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
    needed = num_track_frames + 3
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


def post_json(base_url: str, endpoint: str, payload: dict):
    return requests.post(f"{base_url}{endpoint}", json=payload, timeout=REQUEST_TIMEOUT)


def check_probe_endpoints(base_url: str, expect_ready: bool) -> None:
    health = requests.get(f"{base_url}/healthz", timeout=30)
    health.raise_for_status()
    health_data = health.json()
    assert health_data["status"] == "ok", health_data
    assert "available_weights" in health_data, health_data

    version = requests.get(f"{base_url}/version", timeout=30)
    version.raise_for_status()
    version_data = version.json()
    assert version_data["version"] == "track-advi-http-v1", version_data

    ready = requests.get(f"{base_url}/ready", timeout=30)
    if expect_ready:
        ready.raise_for_status()
        ready_data = ready.json()
        assert ready_data["status"] == "ready", ready_data
        assert ready_data["cached_models"], ready_data
    else:
        assert ready.status_code == 503, ready.text


def get_health(base_url: str) -> dict:
    response = requests.get(f"{base_url}/healthz", timeout=30)
    response.raise_for_status()
    return response.json()


def run_track_sequence(
    base_url: str,
    track_endpoint: str,
    frame_sources: list[Union[Path, str]],
    gt_boxes: list[list[int]],
    cache_version: int,
    output_prefix: str,
) -> list[float]:
    ious: list[float] = []
    for frame_index, (frame_source, gt_box) in enumerate(zip(frame_sources, gt_boxes), start=1):
        if track_endpoint.endswith("/file"):
            response = post_file(base_url, track_endpoint, frame_source)
        else:
            response = post_json(base_url, track_endpoint, {"image_url": frame_source})

        response.raise_for_status()
        data = response.json()
        assert data["cache_version"] == cache_version, data
        assert data["frame_index"] == frame_index, data
        assert isinstance(data["score"], (int, float)), data

        image_path = frame_source if isinstance(frame_source, Path) else Path(frame_source.rsplit("/", 1)[-1])
        if isinstance(frame_source, Path):
            image_size = get_image_size(frame_source)
        else:
            image_size = get_image_size(DATA_ROOT / VIDEO_NAME / image_path.name)

        assert_bbox_valid(data["bbox_xyxy"], image_size)

        tracked_bytes = decode_image(data["tracked_image_base64"])
        save_bytes(f"{output_prefix}_{frame_index:02d}.jpg", tracked_bytes)

        ious.append(bbox_iou(data["bbox_xyxy"], gt_box))
    return ious


def run_file_flow(frames: list[Path], gt_boxes: list[list[int]]) -> dict:
    with run_service() as base_url:
        health_before = get_health(base_url)
        if MANAGED_SERVICE:
            check_probe_endpoints(base_url, expect_ready=False)
            pre_track = post_file(base_url, "/track/file", frames[1])
            assert pre_track.status_code == 400, pre_track.text

        init_bbox = gt_boxes[0]
        init_payload = {"x1": init_bbox[0], "y1": init_bbox[1], "x2": init_bbox[2], "y2": init_bbox[3]}
        init_endpoint = "/template/set/file" if not health_before.get("template_cached") else "/template/replace/file"
        set_resp = post_file(base_url, init_endpoint, frames[0], init_payload)
        set_resp.raise_for_status()
        set_data = set_resp.json()
        expected_status = "created" if init_endpoint.endswith("/set/file") else "replaced"
        assert set_data["status"] == expected_status, set_data
        assert set_data["initial_bbox_xyxy"] == init_bbox, set_data
        save_bytes("file_template_set.jpg", decode_image(set_data["cached_template_base64"]))

        current_cache_version = set_data["cache_version"]

        if MANAGED_SERVICE:
            check_probe_endpoints(base_url, expect_ready=True)

        if MANAGED_SERVICE:
            duplicate_set = post_file(base_url, "/template/set/file", frames[0], init_payload)
            assert duplicate_set.status_code == 400, duplicate_set.text

            duplicate_init = post_file(base_url, "/init/file", frames[0], init_payload)
            assert duplicate_init.status_code == 400, duplicate_init.text

        ious = run_track_sequence(
            base_url=base_url,
            track_endpoint="/track/file",
            frame_sources=frames[1 : NUM_TRACK_FRAMES + 1],
            gt_boxes=gt_boxes[1 : NUM_TRACK_FRAMES + 1],
            cache_version=current_cache_version,
            output_prefix="file_track",
        )

        replace_bbox = gt_boxes[NUM_TRACK_FRAMES + 1]
        replace_payload = {
            "x1": replace_bbox[0],
            "y1": replace_bbox[1],
            "x2": replace_bbox[2],
            "y2": replace_bbox[3],
        }
        replace_resp = post_file(base_url, "/template/replace/file", frames[NUM_TRACK_FRAMES + 1], replace_payload)
        replace_resp.raise_for_status()
        replace_data = replace_resp.json()
        assert replace_data["status"] == "replaced", replace_data
        assert replace_data["initial_bbox_xyxy"] == replace_bbox, replace_data
        save_bytes("file_template_replace.jpg", decode_image(replace_data["cached_template_base64"]))

        post_replace_ious = run_track_sequence(
            base_url=base_url,
            track_endpoint="/track/file",
            frame_sources=[frames[NUM_TRACK_FRAMES + 2]],
            gt_boxes=[gt_boxes[NUM_TRACK_FRAMES + 2]],
            cache_version=replace_data["cache_version"],
            output_prefix="file_track_after_replace",
        )

        return {
            "mode": "file",
            "video": VIDEO_NAME,
            "frames_tracked": NUM_TRACK_FRAMES,
            "mean_iou": sum(ious) / len(ious),
            "max_iou": max(ious),
            "min_iou": min(ious),
            "ious": ious,
            "post_replace_iou": post_replace_ious[0],
        }


def run_file_init_alias_flow(frames: list[Path], gt_boxes: list[list[int]]) -> dict:
    if not MANAGED_SERVICE:
        return {"mode": "file_init_alias", "skipped": True, "reason": "external shared service"}

    with run_service() as base_url:
        init_bbox = gt_boxes[0]
        init_payload = {"x1": init_bbox[0], "y1": init_bbox[1], "x2": init_bbox[2], "y2": init_bbox[3]}
        init_resp = post_file(base_url, "/init/file", frames[0], init_payload)
        init_resp.raise_for_status()
        init_data = init_resp.json()
        assert init_data["status"] == "created", init_data
        assert init_data["cache_version"] == 1, init_data
        assert init_data["initial_bbox_xyxy"] == init_bbox, init_data
        save_bytes("file_init_alias.jpg", decode_image(init_data["cached_template_base64"]))

        alias_ious = run_track_sequence(
            base_url=base_url,
            track_endpoint="/track/file",
            frame_sources=[frames[1]],
            gt_boxes=[gt_boxes[1]],
            cache_version=1,
            output_prefix="file_init_alias_track",
        )
        return {"mode": "file_init_alias", "post_init_iou": alias_ious[0]}


def run_url_flow(frames: list[Path], gt_boxes: list[list[int]]) -> dict:
    video_dir = frames[0].parent
    with run_static_server(video_dir) as image_base_url:
        with run_service() as base_url:
            health_before = get_health(base_url)
            init_bbox = gt_boxes[0]
            init_endpoint = "/init/url" if MANAGED_SERVICE and not health_before.get("template_cached") else "/template/replace/url"
            init_resp = post_json(
                base_url,
                init_endpoint,
                {
                    "image_url": f"{image_base_url}/{frames[0].name}",
                    "initial_bbox_xyxy": init_bbox,
                },
            )
            init_resp.raise_for_status()
            init_data = init_resp.json()
            expected_status = "created" if init_endpoint == "/init/url" else "replaced"
            assert init_data["status"] == expected_status, init_data
            assert init_data["initial_bbox_xyxy"] == init_bbox, init_data
            save_bytes("url_init_template.jpg", decode_image(init_data["cached_template_base64"]))

            current_cache_version = init_data["cache_version"]
            if MANAGED_SERVICE:
                check_probe_endpoints(base_url, expect_ready=True)

            if MANAGED_SERVICE:
                duplicate_set = post_json(
                    base_url,
                    "/template/set/url",
                    {
                        "image_url": f"{image_base_url}/{frames[0].name}",
                        "initial_bbox_xyxy": init_bbox,
                    },
                )
                assert duplicate_set.status_code == 400, duplicate_set.text

            frame_urls = [f"{image_base_url}/{frame.name}" for frame in frames[1 : NUM_TRACK_FRAMES + 1]]
            ious = run_track_sequence(
                base_url=base_url,
                track_endpoint="/track/url",
                frame_sources=frame_urls,
                gt_boxes=gt_boxes[1 : NUM_TRACK_FRAMES + 1],
                cache_version=current_cache_version,
                output_prefix="url_track",
            )

            replace_bbox = gt_boxes[NUM_TRACK_FRAMES + 1]
            replace_resp = post_json(
                base_url,
                "/template/replace/url",
                {
                    "image_url": f"{image_base_url}/{frames[NUM_TRACK_FRAMES + 1].name}",
                    "initial_bbox_xyxy": replace_bbox,
                },
            )
            replace_resp.raise_for_status()
            replace_data = replace_resp.json()
            assert replace_data["status"] == "replaced", replace_data
            assert replace_data["initial_bbox_xyxy"] == replace_bbox, replace_data
            save_bytes("url_template_replace.jpg", decode_image(replace_data["cached_template_base64"]))

            post_replace_ious = run_track_sequence(
                base_url=base_url,
                track_endpoint="/track/url",
                frame_sources=[f"{image_base_url}/{frames[NUM_TRACK_FRAMES + 2].name}"],
                gt_boxes=[gt_boxes[NUM_TRACK_FRAMES + 2]],
                cache_version=replace_data["cache_version"],
                output_prefix="url_track_after_replace",
            )

            return {
                "mode": "url",
                "video": VIDEO_NAME,
                "frames_tracked": NUM_TRACK_FRAMES,
                "mean_iou": sum(ious) / len(ious),
                "max_iou": max(ious),
                "min_iou": min(ious),
                "ious": ious,
                "post_replace_iou": post_replace_ious[0],
            }


def run_url_template_set_alias_flow(frames: list[Path], gt_boxes: list[list[int]]) -> dict:
    if not MANAGED_SERVICE:
        return {"mode": "url_template_set_alias", "skipped": True, "reason": "external shared service"}

    video_dir = frames[0].parent
    with run_static_server(video_dir) as image_base_url:
        with run_service() as base_url:
            init_bbox = gt_boxes[0]
            set_resp = post_json(
                base_url,
                "/template/set/url",
                {
                    "image_url": f"{image_base_url}/{frames[0].name}",
                    "initial_bbox_xyxy": init_bbox,
                },
            )
            set_resp.raise_for_status()
            set_data = set_resp.json()
            assert set_data["status"] == "created", set_data
            assert set_data["cache_version"] == 1, set_data
            assert set_data["initial_bbox_xyxy"] == init_bbox, set_data
            save_bytes("url_template_set_alias.jpg", decode_image(set_data["cached_template_base64"]))

            alias_ious = run_track_sequence(
                base_url=base_url,
                track_endpoint="/track/url",
                frame_sources=[f"{image_base_url}/{frames[1].name}"],
                gt_boxes=[gt_boxes[1]],
                cache_version=1,
                output_prefix="url_template_set_alias_track",
            )
            return {"mode": "url_template_set_alias", "post_set_iou": alias_ious[0]}


def main():
    frames, gt_boxes = load_sequence(VIDEO_NAME, NUM_TRACK_FRAMES)
    OUTPUT_DIR.mkdir(exist_ok=True)

    file_summary = run_file_flow(frames, gt_boxes)
    file_init_alias_summary = run_file_init_alias_flow(frames, gt_boxes)
    url_summary = run_url_flow(frames, gt_boxes)
    url_set_alias_summary = run_url_template_set_alias_flow(frames, gt_boxes)

    summary = {
        "dataset_video": VIDEO_NAME,
        "num_track_frames": NUM_TRACK_FRAMES,
        "dataset_root": str(DATA_ROOT),
        "gt_root": str(GT_ROOT),
        "file_flow": file_summary,
        "file_init_alias_flow": file_init_alias_summary,
        "url_flow": url_summary,
        "url_template_set_alias_flow": url_set_alias_summary,
    }
    summary_path = OUTPUT_DIR / "track_advi_test_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"saved summary: {summary_path}")


if __name__ == "__main__":
    main()
