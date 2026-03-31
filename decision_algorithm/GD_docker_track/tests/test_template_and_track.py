import base64
from pathlib import Path
from typing import Optional

import requests

base_url = "http://127.0.0.1:8002"
assets_dir = Path(__file__).resolve().parent / "assets"
output_dir = Path(__file__).resolve().parent / "outputs"
output_dir.mkdir(exist_ok=True)


def parse_template_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8").strip()
    x, y, w, h = [int(v) for v in text.split(",")]
    return {
        "x1": x,
        "y1": y,
        "x2": x + w,
        "y2": y + h,
    }


def save_image_from_base64(filename: str, encoded: str):
    img_bytes = base64.b64decode(encoded)
    out_path = output_dir / filename
    out_path.write_bytes(img_bytes)
    print("saved:", out_path)


def post_file(url: str, image_path: Path, data: Optional[dict] = None):
    with image_path.open("rb") as f:
        resp = requests.post(
            f"{base_url}{url}",
            data=data or {},
            files={"image": (image_path.name, f, "image/jpeg")},
            timeout=60,
        )
    return resp


def print_step(title: str):
    print(f"\n=== {title} ===")


def print_json(resp):
    print("status_code:", resp.status_code)
    print(resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text)


frame_paths = sorted(assets_dir.glob("*.jpg"))
assert len(frame_paths) >= 6, "need at least 6 jpg frames in tests/assets"
initial_bbox = parse_template_file(assets_dir / "template.txt")

init_frame = frame_paths[0]
track_frames = frame_paths[1:6]
replace_frame = frame_paths[6]
post_replace_track_frames = frame_paths[7:10]

print_step("health_before_init")
resp = requests.get(f"{base_url}/healthz", timeout=30)
resp.raise_for_status()
print_json(resp)

print_step("track_should_fail_before_init")
resp = post_file("/track/file", track_frames[0])
print("status_code:", resp.status_code)
print("body:", resp.text)

print_step("init_with_first_raw_frame_and_initial_bbox")
resp = post_file("/init/file", init_frame, data=initial_bbox)
resp.raise_for_status()
init_data = resp.json()
print(init_data)
save_image_from_base64("init_template_preview.jpg", init_data["cached_template_base64"])

print_step("health_after_init")
resp = requests.get(f"{base_url}/healthz", timeout=30)
resp.raise_for_status()
print_json(resp)

for idx, frame_path in enumerate(track_frames, start=1):
    print_step(f"track_frame_{idx}_{frame_path.name}")
    resp = post_file("/track/file", frame_path)
    resp.raise_for_status()
    data = resp.json()
    print(data)
    save_image_from_base64(f"tracked_{frame_path.stem}.jpg", data["tracked_image_base64"])

print_step("health_after_first_tracking_segment")
resp = requests.get(f"{base_url}/healthz", timeout=30)
resp.raise_for_status()
print_json(resp)

replace_bbox = {
    "x1": max(0, initial_bbox["x1"] - 10),
    "y1": max(0, initial_bbox["y1"] - 10),
    "x2": max(initial_bbox["x1"] + 20, initial_bbox["x2"] - 10),
    "y2": max(initial_bbox["y1"] + 20, initial_bbox["y2"] - 10),
}

print_step(f"replace_template_with_{replace_frame.name}")
resp = post_file("/template/replace/file", replace_frame, data=replace_bbox)
resp.raise_for_status()
replace_data = resp.json()
print(replace_data)
save_image_from_base64("replaced_template_preview.jpg", replace_data["cached_template_base64"])

print_step("health_after_replace")
resp = requests.get(f"{base_url}/healthz", timeout=30)
resp.raise_for_status()
print_json(resp)

for idx, frame_path in enumerate(post_replace_track_frames, start=1):
    print_step(f"track_after_replace_{idx}_{frame_path.name}")
    resp = post_file("/track/file", frame_path)
    resp.raise_for_status()
    data = resp.json()
    print(data)
    save_image_from_base64(f"tracked_after_replace_{frame_path.stem}.jpg", data["tracked_image_base64"])
