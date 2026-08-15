#!/usr/bin/env python3
"""
Rebuild the first captured RDMA image payload into a pure 1024x1024 raw image.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "sdk" / "python"))

from midware import RDMA_IMAGE_RAW_SIZE, RDMA_IMAGE_REBUILT_SIZE, rebuild_rdma_image  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Rebuild the first captured type=3 image payload.")
    parser.add_argument("capture", nargs="?", default=str(ROOT / "captures"),
                        help="Capture directory containing manifest.json")
    parser.add_argument("--output", default="first_image_1024x1024.raw",
                        help="Output raw grayscale image path")
    return parser.parse_args()


def main():
    args = parse_args()
    capture_dir = Path(args.capture)
    manifest = json.loads((capture_dir / "manifest.json").read_text(encoding="utf-8"))

    image_packet = None
    for pkt in manifest["packets"]:
        if pkt["source"] == "rdma-prod-2" and pkt["type"] == 3:
            image_packet = pkt
            break

    if image_packet is None:
        raise SystemExit("No rdma-prod-2 type=3 image payload found.")

    raw_payload = (capture_dir / image_packet["file"]).read_bytes()
    image = rebuild_rdma_image(raw_payload)
    Path(args.output).write_bytes(image)

    print(f"input_file={image_packet['file']}")
    print(f"raw_payload_len={len(raw_payload)} expected={RDMA_IMAGE_RAW_SIZE}")
    print(f"rebuilt_image_len={len(image)} expected={RDMA_IMAGE_REBUILT_SIZE}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
