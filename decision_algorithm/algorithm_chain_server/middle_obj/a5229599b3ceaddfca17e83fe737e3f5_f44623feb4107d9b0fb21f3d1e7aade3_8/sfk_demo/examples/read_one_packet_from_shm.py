#!/usr/bin/env python3
"""
Read one middleware packet from a SHM stream using the Python SDK.
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "sdk" / "python"))

from midware import ShmConsumer, TYPE_RDMA_IMAGE_RAW, rebuild_rdma_image  # noqa: E402


DEFAULT_SHM_BY_SOURCE = {
    "rdma-prod-1": "/dev/shm/shm-cons-sim-1",
    "rdma-prod-2": "/dev/shm/shm-cons-sim-2",
    "rdma-prod-3": "/dev/shm/shm-cons-sim-3",
    "rdma-prod-4": "/dev/shm/shm-cons-sim-4",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Read one packet from a middleware SHM stream.")
    parser.add_argument("--source", default="rdma-prod-2", choices=sorted(DEFAULT_SHM_BY_SOURCE),
                        help="Source name to read from")
    parser.add_argument("--shm", help="Override SHM path")
    parser.add_argument("--timeout", type=float, default=5.0, help="Seconds to wait for a packet")
    return parser.parse_args()


def main():
    args = parse_args()
    shm_path = args.shm or DEFAULT_SHM_BY_SOURCE[args.source]
    consumer = ShmConsumer(shm_path)

    deadline = time.time() + args.timeout
    pkt = None
    while time.time() < deadline:
        pkt = consumer.read_packet()
        if pkt is not None:
            break
        time.sleep(0.01)
    consumer.close()

    if pkt is None:
        raise SystemExit(f"No packet received from {shm_path} within {args.timeout}s")

    print(f"source={args.source}")
    print(f"shm={shm_path}")
    print(f"type={pkt.type}")
    print(f"timestamp_us={pkt.timestamp_us}")
    print(f"payload_len={len(pkt.payload)}")

    if pkt.type == TYPE_RDMA_IMAGE_RAW:
        image = rebuild_rdma_image(pkt.payload)
        print(f"rebuilt_image_len={len(image)}")


if __name__ == "__main__":
    main()
