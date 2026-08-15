#!/usr/bin/env python3
"""
Replay payload-only capture data into middleware-compatible SHM streams.

Input:
  captures/manifest.json
  captures/*.bin

Each .bin file is payload-only. This script uses the Python SDK to wrap it
with the recorded type/timestamp header and write it to the matching SHM.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
LOCAL_SDK_DIR = SCRIPT_DIR / "sdk" / "python"
REPO_SDK_DIR = SCRIPT_DIR.parent / "sdk" / "python"
SDK_DIR = LOCAL_SDK_DIR if LOCAL_SDK_DIR.exists() else REPO_SDK_DIR
sys.path.append(str(SDK_DIR))

from midware import ShmProducer  # noqa: E402


HEADER_SIZE = 13
MIN_SLOT_SIZE = 64 * 1024

DEFAULT_SOURCE_PATHS = {
    "rdma-prod-1": "/dev/shm/shm-cons-sim-1",
    "rdma-prod-2": "/dev/shm/shm-cons-sim-2",
    "rdma-prod-3": "/dev/shm/shm-cons-sim-3",
    "rdma-prod-4": "/dev/shm/shm-cons-sim-4",
}


def load_manifest(path: Path):
    if path.is_dir():
        manifest_path = path / "manifest.json"
    else:
        manifest_path = path

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    return manifest_path.parent, manifest


def build_source_paths(args, manifest):
    paths = dict(DEFAULT_SOURCE_PATHS)
    for source, info in manifest.get("sources", {}).items():
        shm_path = info.get("shm_path")
        if shm_path:
            paths[source] = shm_path

    paths["rdma-prod-1"] = args.timestamp_shm
    paths["rdma-prod-2"] = args.image_shm
    paths["rdma-prod-3"] = args.gyro_shm
    paths["rdma-prod-4"] = args.encoder_shm
    return paths


def select_packets(manifest, sources, limit):
    packets = list(manifest.get("packets", []))
    if sources:
        wanted = set(sources)
        packets = [pkt for pkt in packets if pkt.get("source") in wanted]
    packets.sort(key=lambda item: (
        item.get("captured_at_unix_ns", 0),
        item.get("source", ""),
        item.get("index", 0),
    ))
    if limit is not None:
        packets = packets[:limit]
    return packets


def open_producers(packets, source_paths):
    max_packet_by_source = {}
    for pkt in packets:
        source = pkt["source"]
        payload_len = int(pkt.get("payload_len", 0))
        max_packet_by_source[source] = max(
            max_packet_by_source.get(source, 0),
            payload_len + HEADER_SIZE,
        )

    producers = {}
    slot_sizes = {}
    for source, max_packet_len in sorted(max_packet_by_source.items()):
        shm_path = source_paths.get(source)
        if not shm_path:
            raise ValueError(f"no SHM path configured for source {source}")

        slot_size = max(MIN_SLOT_SIZE, max_packet_len)
        slot_sizes[source] = slot_size
        producers[source] = ShmProducer(shm_path, slot_size)
        print(f"[replay] {source} -> {shm_path} (slot_size={slot_size})")

    return producers, slot_sizes


def ensure_producers_visible(producers, source_paths, slot_sizes):
    for source, producer in list(producers.items()):
        shm_path = source_paths[source]
        if os.path.exists(shm_path):
            continue

        print(f"[replay] SHM path disappeared, recreating: {source} -> {shm_path}")
        producer.close()
        producers[source] = ShmProducer(shm_path, slot_sizes[source])


def replay_once(root: Path, packets, producers, timing: str, rate: float):
    sent = 0
    failed = 0
    prev_capture_ns = None

    for pkt in packets:
        capture_ns = int(pkt.get("captured_at_unix_ns", 0))
        if timing == "captured" and prev_capture_ns is not None and capture_ns > prev_capture_ns:
            delta_sec = (capture_ns - prev_capture_ns) / 1_000_000_000 / rate
            if delta_sec > 0:
                time.sleep(delta_sec)
        prev_capture_ns = capture_ns

        source = pkt["source"]
        payload_path = root / pkt["file"]
        payload = payload_path.read_bytes()
        expected_len = int(pkt.get("payload_len", len(payload)))
        if len(payload) != expected_len:
            print(f"[replay] WARN length mismatch: {payload_path} expected={expected_len} actual={len(payload)}")

        ok = producers[source].write_packet(
            payload,
            type_id=int(pkt["type"]),
            timestamp_us=int(pkt["timestamp_us"]),
        )
        if ok:
            sent += 1
        else:
            failed += 1

    return sent, failed


def parse_args():
    parser = argparse.ArgumentParser(
        description="Replay captured payload-only files into middleware-compatible SHM streams."
    )
    parser.add_argument("capture", help="Capture directory or manifest.json path")
    parser.add_argument("--timing", choices=("captured", "none"), default="captured",
                        help="Replay using captured wall-clock intervals, or as fast as possible.")
    parser.add_argument("--rate", type=float, default=1.0,
                        help="Timing multiplier for --timing captured. 2.0 means twice as fast.")
    parser.add_argument("--loop", action="store_true", help="Replay repeatedly until interrupted.")
    parser.add_argument("--repeat-delay", type=float, default=1.0,
                        help="Delay between loops when --loop is set.")
    parser.add_argument("--source", action="append",
                        help="Replay only one source. May be specified multiple times.")
    parser.add_argument("--limit", type=int, help="Replay at most N packets.")
    parser.add_argument("--timestamp-shm", default=os.getenv("TIMESTAMP_SHM_PATH", "/dev/shm/shm-cons-sim-1"))
    parser.add_argument("--image-shm", default=os.getenv("IMAGE_SHM_PATH", "/dev/shm/shm-cons-sim-2"))
    parser.add_argument("--gyro-shm", default=os.getenv("GYRO_SHM_PATH", "/dev/shm/shm-cons-sim-3"))
    parser.add_argument("--encoder-shm", default=os.getenv("ENCODER_SHM_PATH", "/dev/shm/shm-cons-sim-4"))
    return parser.parse_args()


def main():
    args = parse_args()
    if args.rate <= 0:
        raise SystemExit("--rate must be > 0")

    root, manifest = load_manifest(Path(args.capture))
    if not manifest.get("payload_only", False):
        raise SystemExit("manifest is not marked as payload_only")

    packets = select_packets(manifest, args.source, args.limit)
    if not packets:
        raise SystemExit("no packets selected for replay")

    source_paths = build_source_paths(args, manifest)
    producers, slot_sizes = open_producers(packets, source_paths)

    print(f"[replay] packets={len(packets)} timing={args.timing} rate={args.rate}")
    try:
        loop_count = 0
        while True:
            loop_count += 1
            ensure_producers_visible(producers, source_paths, slot_sizes)
            sent, failed = replay_once(root, packets, producers, args.timing, args.rate)
            print(f"[replay] loop={loop_count} sent={sent} failed={failed}")
            if not args.loop:
                break
            time.sleep(args.repeat_delay)
    except KeyboardInterrupt:
        print("\n[replay] interrupted")
    finally:
        for producer in producers.values():
            producer.close()


if __name__ == "__main__":
    main()
