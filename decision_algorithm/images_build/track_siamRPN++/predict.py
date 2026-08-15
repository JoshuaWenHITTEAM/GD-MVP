from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from app.inference.backends.siamrpnpp_runtime import SiamRPNPPRuntime
from app.inference.io_utils import annotate_bbox, encode_rgb_to_jpeg_bytes, load_image_to_rgb
from app.schemas import TrackInput


PROJECT_ROOT = Path(__file__).resolve().parent


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"config root must be a mapping: {path}")
    return data


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def load_gt_xyxy(gt_path: Path) -> List[List[int]]:
    gt = []
    for line in gt_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        x, y, w, h = [int(float(v)) for v in line.split()]
        gt.append([x, y, x + w, y + h])
    return gt


def load_sequence(sequence_dir: Path) -> List[Path]:
    frames = sorted(sequence_dir.glob("*.jpg"))
    if not frames:
        raise FileNotFoundError(f"no jpg frames found in {sequence_dir}")
    return frames


def save_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def build_runtime(config_data: Dict[str, Any]) -> SiamRPNPPRuntime:
    model_cfg = config_data.get("model", {})
    config_path = resolve_path(model_cfg.get("config_path", "configs/siamrpnpp.yaml"))
    weight_path = resolve_path(model_cfg.get("weight_path", "models/siamrpnpp.pth"))
    import torch

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    return SiamRPNPPRuntime(config_path=config_path, weight_path=weight_path, device=device)


def main() -> None:
    parser = argparse.ArgumentParser(description="SiamRPN++ sequence prediction")
    parser.add_argument("--config", default="configs/predict.yaml", help="predict yaml path")
    parser.add_argument("--sequence-dir", help="override sequence directory")
    parser.add_argument("--gt-file", help="override gt file path")
    parser.add_argument("--num-frames", type=int, help="override number of tracking frames")
    parser.add_argument("--output-dir", help="override output directory")
    args = parser.parse_args()

    config_path = resolve_path(args.config)
    config_data = load_yaml(config_path)
    input_cfg = config_data.get("input", {})
    output_cfg = config_data.get("output", {})

    sequence_dir = resolve_path(args.sequence_dir or input_cfg.get("sequence_dir"))
    gt_file: Optional[str] = args.gt_file or input_cfg.get("gt_file")
    num_track_frames = int(args.num_frames or input_cfg.get("num_track_frames", 20))
    output_dir = resolve_path(args.output_dir or output_cfg.get("output_dir", "outputs/predict"))

    frames = load_sequence(sequence_dir)
    if gt_file is None:
        raise ValueError("gt_file is required")
    gt = load_gt_xyxy(resolve_path(gt_file))
    if len(gt) < num_track_frames + 1:
        raise ValueError(f"gt entries not enough for {num_track_frames} frames: {len(gt)}")
    if len(frames) < num_track_frames + 1:
        raise ValueError(f"frames not enough for {num_track_frames} frames: {len(frames)}")

    runtime = build_runtime(config_data)

    first_rgb = load_image_to_rgb(TrackInput(image_bytes=frames[0].read_bytes()))
    template = runtime.prepare_template(first_rgb, gt[0])
    save_bytes(output_dir / "template.jpg", encode_rgb_to_jpeg_bytes(template.template_rgb))

    records = []
    for idx in range(1, num_track_frames + 1):
        frame_path = frames[idx]
        image_rgb = load_image_to_rgb(TrackInput(image_bytes=frame_path.read_bytes()))
        tracked = runtime.track(image_rgb)
        annotated = annotate_bbox(image_rgb, tracked.bbox_xyxy)
        save_bytes(output_dir / f"track_{idx:02d}.jpg", encode_rgb_to_jpeg_bytes(annotated))
        records.append(
            {
                "frame_index": idx,
                "image_name": frame_path.name,
                "bbox_xyxy": tracked.bbox_xyxy,
                "score": tracked.score,
                "gt_bbox_xyxy": gt[idx],
            }
        )

    save_bytes(
        output_dir / "summary.json",
        json.dumps(
            {
                "sequence_dir": str(sequence_dir),
                "gt_file": str(resolve_path(gt_file)),
                "num_track_frames": num_track_frames,
                "records": records,
            },
            indent=2,
            ensure_ascii=False,
        ).encode("utf-8"),
    )


if __name__ == "__main__":
    main()
