import base64
from concurrent.futures import Future, ThreadPoolExecutor
import contextlib
import io
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image
import requests
try:
    import cv2
except ModuleNotFoundError:
    cv2 = None


DEFAULT_DATASET_ROOT = Path(os.environ.get("DATASET_ROOT", "./datasets/Anti-UAV-Tracking-V0"))
DEFAULT_SEQUENCES = ("video10", "video20")
SCENARIO_MID_GAP = "mid_gap"
SCENARIO_SEQUENCE_TRANSITION = "sequence_transition"
SUPPORTED_SCENARIOS = (SCENARIO_MID_GAP, SCENARIO_SEQUENCE_TRANSITION)


@dataclass(frozen=True)
class DetectorConfig:
    name: str
    base_url: str
    model_name: str


@dataclass(frozen=True)
class TrackerConfig:
    name: str
    base_url: str


@dataclass(frozen=True)
class PreparedFrame:
    sequence_name: str
    frame_index: int
    frame_path: Path
    probe_reason: Optional[str]
    frame_bytes: bytes
    processed_bytes: bytes
    preprocess_timings_ms: dict[str, float]
    read_frame_ms: float
    raw_rgb_bytes: bytes
    raw_width: int
    raw_height: int
    raw_prepare_ms: float
    prepare_total_ms: float


DEFAULT_DETECTOR = DetectorConfig(
    name="yolov8",
    base_url="http://127.0.0.1:8004",
    model_name="anti_uav_yolov8n",
)
DEFAULT_TRACKER = TrackerConfig(
    name="avtrack",
    base_url="http://127.0.0.1:8002",
)
DEFAULT_MID_SEQUENCE_PROBE_SCORE_THRESHOLD = 0.78
DEFAULT_MID_SEQUENCE_SKIP_FRAMES = 96
DEFAULT_MID_SEQUENCE_GAP_START_RATIO = 0.28
DEFAULT_TRANSITION_SKIP_FRAMES = 0


def resolve_dataset_dir(dataset_root: Path) -> Path:
    candidates = (
        dataset_root,
        dataset_root / "Anti-UAV-Tracking-V0",
        dataset_root / "Anti-UAV-Tracking-V0" / "Anti-UAV-Tracking-V0",
    )
    for candidate in candidates:
        if candidate.is_dir() and any(path.is_dir() for path in candidate.glob("video*")):
            return candidate
    raise FileNotFoundError(f"unable to resolve sequence directory under: {dataset_root}")


def load_sequence_frames(dataset_root: Path, sequence_name: str, max_frames: int) -> list[Path]:
    sequence_dir = resolve_dataset_dir(dataset_root) / sequence_name
    if not sequence_dir.is_dir():
        raise FileNotFoundError(f"sequence not found: {sequence_dir}")
    frames = sorted(sequence_dir.glob("*.jpg"))
    if not frames:
        raise ValueError(f"no jpg frames found under: {sequence_dir}")
    return frames[:max_frames] if max_frames > 0 else frames


def parse_detection_bbox(detection: dict) -> list[int]:
    if {"x1", "y1", "x2", "y2"}.issubset(detection):
        return [int(detection["x1"]), int(detection["y1"]), int(detection["x2"]), int(detection["y2"])]

    box = detection.get("box")
    if isinstance(box, dict) and {"x1", "y1", "x2", "y2"}.issubset(box):
        return [int(box["x1"]), int(box["y1"]), int(box["x2"]), int(box["y2"])]

    bbox_xyxy = detection.get("bbox_xyxy")
    if isinstance(bbox_xyxy, dict) and {"x1", "y1", "x2", "y2"}.issubset(bbox_xyxy):
        return [
            int(bbox_xyxy["x1"]),
            int(bbox_xyxy["y1"]),
            int(bbox_xyxy["x2"]),
            int(bbox_xyxy["y2"]),
        ]

    raise ValueError(f"unsupported detection bbox format: {detection}")


def select_best_detection(detections: list[dict]) -> Optional[dict]:
    if not detections:
        return None
    return max(detections, key=lambda item: float(item.get("confidence", item.get("score", 0.0))))


def encode_image_bytes(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


def bbox_is_reasonable(bbox_xyxy: list[int]) -> bool:
    x1, y1, x2, y2 = bbox_xyxy
    return x2 > x1 and y2 > y1


class ServiceClient:
    def __init__(self, detector: DetectorConfig, tracker: TrackerConfig):
        self.detector = detector
        self.tracker = tracker
        self._sessions: dict[str, requests.Session] = {}

    def preprocess(self, image_bytes: bytes) -> tuple[bytes, str, dict[str, float]]:
        return image_bytes, "none", {
            "chain_preprocess_quality_estimate_ms": 0.0,
            "chain_preprocess_apply_ms": 0.0,
            "chain_preprocess_total_ms": 0.0,
        }

    def close(self) -> None:
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()

    def _session(self, base_url: str) -> requests.Session:
        session = self._sessions.get(base_url)
        if session is not None:
            return session
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=8)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        self._sessions[base_url] = session
        return session

    def _post_image(self, base_url: str, endpoint: str, filename: str, image_bytes: bytes, data: dict) -> tuple[dict, float]:
        started_at = time.perf_counter()
        response = self._session(base_url).post(
            f"{base_url}{endpoint}",
            data=data,
            files={"image": (filename, io.BytesIO(image_bytes), "image/jpeg")},
            timeout=300,
        )
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        response.raise_for_status()
        return response.json(), latency_ms

    def _post_raw_image(
        self,
        base_url: str,
        endpoint: str,
        filename: str,
        raw_rgb_bytes: bytes,
        width: int,
        height: int,
        data: dict,
    ) -> tuple[dict, float]:
        started_at = time.perf_counter()
        response = self._session(base_url).post(
            f"{base_url}{endpoint}",
            data={
                **data,
                "width": str(width),
                "height": str(height),
                "channels": "3",
            },
            files={"image": (filename, io.BytesIO(raw_rgb_bytes), "application/octet-stream")},
            timeout=300,
        )
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        response.raise_for_status()
        return response.json(), latency_ms

    def _post_raw_body(
        self,
        base_url: str,
        endpoint: str,
        raw_rgb_bytes: bytes,
        width: int,
        height: int,
        data: dict,
    ) -> tuple[dict, float]:
        started_at = time.perf_counter()
        response = self._session(base_url).post(
            f"{base_url}{endpoint}",
            params={
                **data,
                "width": str(width),
                "height": str(height),
                "channels": "3",
            },
            data=raw_rgb_bytes,
            headers={"Content-Type": "application/octet-stream"},
            timeout=300,
        )
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        response.raise_for_status()
        return response.json(), latency_ms

    def _image_bytes_to_raw_rgb(self, image_bytes: bytes) -> tuple[bytes, int, int]:
        if cv2 is not None:
            encoded = np.frombuffer(image_bytes, dtype=np.uint8)
            image_bgr = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            if image_bgr is not None:
                image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
                height, width, _ = image_rgb.shape
                return image_rgb.tobytes(), width, height
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image_array = np.asarray(image, dtype=np.uint8)
        height, width, _ = image_array.shape
        return image_array.tobytes(), width, height

    def check_ready(self) -> None:
        for base_url in (self.detector.base_url, self.tracker.base_url):
            response = self._session(base_url).get(f"{base_url}/healthz", timeout=30)
            response.raise_for_status()

    def detect(self, frame_name: str, image_bytes: bytes) -> tuple[dict, float]:
        return self._post_image(
            self.detector.base_url,
            "/infer/file",
            frame_name,
            image_bytes,
            {
                "model_name": self.detector.model_name,
                "return_image": "false",
                "return_yolo_txt": "false",
            },
        )

    def init_tracker(self, frame_name: str, image_bytes: bytes, bbox_xyxy: list[int]) -> tuple[dict, float]:
        return self._post_image(
            self.tracker.base_url,
            "/template/replace/file",
            frame_name,
            image_bytes,
            {
                "x1": bbox_xyxy[0],
                "y1": bbox_xyxy[1],
                "x2": bbox_xyxy[2],
                "y2": bbox_xyxy[3],
                "return_image": "false",
            },
        )

    def track_prepared(
        self,
        frame_name: str,
        image_bytes: bytes,
        raw_rgb_bytes: bytes,
        width: int,
        height: int,
        raw_prepare_ms: float,
    ) -> tuple[dict, float]:
        try:
            response, latency_ms = self._post_raw_body(
                self.tracker.base_url,
                "/track/raw-body",
                raw_rgb_bytes,
                width,
                height,
                {"return_image": "false"},
            )
            timings_ms = response.setdefault("timings_ms", {})
            timings_ms["track_chain_raw_prepare_ms"] = round(raw_prepare_ms, 3)
            return response, latency_ms
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                raise
        try:
            response, latency_ms = self._post_raw_image(
                self.tracker.base_url,
                "/track/raw",
                f"{Path(frame_name).stem}.rgb",
                raw_rgb_bytes,
                width,
                height,
                {"return_image": "false"},
            )
            timings_ms = response.setdefault("timings_ms", {})
            timings_ms["track_chain_raw_prepare_ms"] = round(raw_prepare_ms, 3)
            return response, latency_ms
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                raise
            response, latency_ms = self._post_image(
                self.tracker.base_url,
                "/track/file",
                frame_name,
                image_bytes,
                {"return_image": "false"},
            )
            timings_ms = response.setdefault("timings_ms", {})
            timings_ms["track_chain_raw_prepare_ms"] = round(raw_prepare_ms, 3)
            return response, latency_ms

    def track(self, frame_name: str, image_bytes: bytes) -> tuple[dict, float]:
        raw_started_at = time.perf_counter()
        raw_rgb_bytes, width, height = self._image_bytes_to_raw_rgb(image_bytes)
        raw_prepare_ms = (time.perf_counter() - raw_started_at) * 1000.0
        return self.track_prepared(frame_name, image_bytes, raw_rgb_bytes, width, height, raw_prepare_ms)


class SimpleChainRunner:
    def __init__(
        self,
        *,
        dataset_root: Path = DEFAULT_DATASET_ROOT,
        sequences: tuple[str, ...] = DEFAULT_SEQUENCES,
        scenario: str = SCENARIO_SEQUENCE_TRANSITION,
        detector: DetectorConfig = DEFAULT_DETECTOR,
        tracker: TrackerConfig = DEFAULT_TRACKER,
        max_frames_per_sequence: int = 48,
        detect_score_threshold: float = 0.2,
        track_score_threshold: float = 0.15,
        sequence_transition_score_threshold: float = 0.45,
        mid_sequence_probe_score_threshold: float = DEFAULT_MID_SEQUENCE_PROBE_SCORE_THRESHOLD,
        mid_sequence_skip_frames: int = DEFAULT_MID_SEQUENCE_SKIP_FRAMES,
        mid_sequence_gap_start_ratio: float = DEFAULT_MID_SEQUENCE_GAP_START_RATIO,
        transition_skip_frames: int = DEFAULT_TRANSITION_SKIP_FRAMES,
        frame_interval_s: float = 0.0,
        stop_event: Optional[threading.Event] = None,
    ):
        if scenario not in SUPPORTED_SCENARIOS:
            raise ValueError(f"unsupported scenario: {scenario}")
        self.dataset_root = dataset_root
        self.sequences = sequences
        self.scenario = scenario
        self.max_frames_per_sequence = max_frames_per_sequence
        self.detect_score_threshold = detect_score_threshold
        self.track_score_threshold = track_score_threshold
        self.sequence_transition_score_threshold = sequence_transition_score_threshold
        self.mid_sequence_probe_score_threshold = mid_sequence_probe_score_threshold
        self.mid_sequence_skip_frames = mid_sequence_skip_frames
        self.mid_sequence_gap_start_ratio = mid_sequence_gap_start_ratio
        self.transition_skip_frames = transition_skip_frames
        self.frame_interval_s = frame_interval_s
        self.stop_event = stop_event or threading.Event()
        self.client = ServiceClient(detector=detector, tracker=tracker)

    def close(self) -> None:
        self.client.close()

    def stop(self) -> None:
        self.stop_event.set()
        with contextlib.suppress(Exception):
            self.client.close()

    def stopped(self) -> bool:
        return self.stop_event.is_set()

    def _wait_or_stopped(self) -> bool:
        if self.frame_interval_s <= 0:
            return self.stopped()
        return self.stop_event.wait(self.frame_interval_s)

    def validate(self) -> None:
        self.client.check_ready()
        for sequence_name in self.active_sequences:
            load_sequence_frames(self.dataset_root, sequence_name, self.max_frames_per_sequence)

    @property
    def active_sequences(self) -> tuple[str, ...]:
        if self.scenario == SCENARIO_MID_GAP:
            return (self.sequences[0],)
        return self.sequences[:2]

    def _build_detect_event(
        self,
        *,
        sequence_name: str,
        frame_index: int,
        frame_name: str,
        source_bytes: bytes,
        detection_response: dict,
        detection_score: float,
        bbox_xyxy: list[int],
        reason: str,
        latency_ms: float,
        chain_timings_ms: Optional[dict[str, float]] = None,
    ) -> dict:
        result_timings_ms = {
            "detect_container_http_latency_ms": round(latency_ms, 3),
        }
        if chain_timings_ms:
            result_timings_ms.update(
                {
                    str(key): round(float(value), 3)
                    for key, value in chain_timings_ms.items()
                    if isinstance(value, (int, float))
                }
            )
        return {
            "stage": "detect",
            "sequence": sequence_name,
            "frame_index": frame_index,
            "frame_name": frame_name,
            "reason": reason,
            "_image_bytes": source_bytes,
            "_image_media_type": "image/jpeg",
            "result": {
                "detector": self.client.detector.name,
                "bbox_xyxy": bbox_xyxy,
                "score": round(float(detection_score), 6),
                "num_detections": int(detection_response.get("num_detections", 0)),
                "latency_ms": round(latency_ms, 3),
                "timings_ms": result_timings_ms,
            },
        }

    def _build_track_event(
        self,
        *,
        sequence_name: str,
        frame_index: int,
        frame_name: str,
        source_bytes: bytes,
        track_response: dict,
        latency_ms: float,
        chain_timings_ms: Optional[dict[str, float]] = None,
        reason: Optional[str] = None,
    ) -> dict:
        result_timings_ms = {
            "track_container_http_latency_ms": round(latency_ms, 3),
        }
        if chain_timings_ms:
            result_timings_ms.update(
                {
                    str(key): round(float(value), 3)
                    for key, value in chain_timings_ms.items()
                    if isinstance(value, (int, float))
                }
            )
        response_timings_ms = track_response.get("timings_ms")
        if isinstance(response_timings_ms, dict):
            result_timings_ms.update(
                {
                    str(key): round(float(value), 3)
                    for key, value in response_timings_ms.items()
                    if isinstance(value, (int, float))
                }
            )
        result = {
            "tracker": self.client.tracker.name,
            "bbox_xyxy": [int(round(float(item))) for item in track_response["bbox_xyxy"]],
            "score": round(float(track_response["score"]), 6),
            "cache_version": int(track_response["cache_version"]),
            "latency_ms": round(latency_ms, 3),
            "timings_ms": result_timings_ms,
        }
        return {
            "stage": "track",
            "sequence": sequence_name,
            "frame_index": frame_index,
            "frame_name": frame_name,
            "reason": reason,
            "_image_bytes": source_bytes,
            "_image_media_type": "image/jpeg",
            "result": result,
        }

    def _should_redetect(
        self,
        *,
        probe_reason: Optional[str],
        track_response: dict,
    ) -> tuple[bool, Optional[str]]:
        score = float(track_response["score"])
        bbox_xyxy = [int(round(float(item))) for item in track_response["bbox_xyxy"]]
        if not bbox_is_reasonable(bbox_xyxy):
            return True, "invalid_bbox"
        if score < self.track_score_threshold:
            return True, "track_score_low"
        if probe_reason == "sequence_transition_probe" and score < self.sequence_transition_score_threshold:
            return True, "scene_transition_check"
        if probe_reason == "mid_sequence_gap_probe" and score < self.mid_sequence_probe_score_threshold:
            return True, "intra_sequence_gap_check"
        return False, None

    def _build_frame_plan(self, frames: list[Path], sequence_index: int) -> list[tuple[int, Path, Optional[str]]]:
        if self.scenario == SCENARIO_SEQUENCE_TRANSITION and sequence_index > 0:
            start_offset = min(self.transition_skip_frames, max(len(frames) - 1, 0))
            return [
                (
                    int(frame_path.stem) - 1 if frame_path.stem.isdigit() else frame_idx,
                    frame_path,
                    "sequence_transition_probe" if frame_idx == start_offset else None,
                )
                for frame_idx, frame_path in enumerate(frames[start_offset:], start=start_offset)
            ]

        if self.scenario != SCENARIO_MID_GAP or self.mid_sequence_skip_frames <= 0 or len(frames) < (self.mid_sequence_skip_frames + 6):
            return [
                (
                    int(frame_path.stem) - 1 if frame_path.stem.isdigit() else frame_idx,
                    frame_path,
                    None,
                )
                for frame_idx, frame_path in enumerate(frames)
            ]

        max_gap_start = max(len(frames) - self.mid_sequence_skip_frames - 1, 1)
        gap_start = max(int(len(frames) * self.mid_sequence_gap_start_ratio), 1)
        gap_start = min(gap_start, max_gap_start)
        gap_end = min(gap_start + self.mid_sequence_skip_frames, len(frames) - 1)
        planned = []
        for frame_idx, frame_path in enumerate(frames):
            if gap_start <= frame_idx < gap_end:
                continue
            probe_reason = "mid_sequence_gap_probe" if frame_idx == gap_end else None
            planned.append(
                (
                    int(frame_path.stem) - 1 if frame_path.stem.isdigit() else frame_idx,
                    frame_path,
                    probe_reason,
                )
            )
        return planned

    def _prepare_frame(
        self,
        *,
        sequence_name: str,
        frame_index: int,
        frame_path: Path,
        probe_reason: Optional[str],
    ) -> PreparedFrame:
        prepare_started_at = time.perf_counter()
        read_started_at = time.perf_counter()
        frame_bytes = frame_path.read_bytes()
        read_frame_ms = (time.perf_counter() - read_started_at) * 1000.0

        processed_bytes, _, preprocess_timings_ms = self.client.preprocess(frame_bytes)

        raw_started_at = time.perf_counter()
        raw_rgb_bytes, raw_width, raw_height = self.client._image_bytes_to_raw_rgb(processed_bytes)
        raw_prepare_ms = (time.perf_counter() - raw_started_at) * 1000.0

        prepare_total_ms = (time.perf_counter() - prepare_started_at) * 1000.0
        return PreparedFrame(
            sequence_name=sequence_name,
            frame_index=frame_index,
            frame_path=frame_path,
            probe_reason=probe_reason,
            frame_bytes=frame_bytes,
            processed_bytes=processed_bytes,
            preprocess_timings_ms=preprocess_timings_ms,
            read_frame_ms=read_frame_ms,
            raw_rgb_bytes=raw_rgb_bytes,
            raw_width=raw_width,
            raw_height=raw_height,
            raw_prepare_ms=raw_prepare_ms,
            prepare_total_ms=prepare_total_ms,
        )

    def _submit_prepare_frame(
        self,
        executor: ThreadPoolExecutor,
        sequence_name: str,
        frame_item: tuple[int, Path, Optional[str]],
    ) -> Future[PreparedFrame]:
        frame_index, frame_path, probe_reason = frame_item
        return executor.submit(
            self._prepare_frame,
            sequence_name=sequence_name,
            frame_index=frame_index,
            frame_path=frame_path,
            probe_reason=probe_reason,
        )

    def _detect_and_init(
        self,
        *,
        sequence_name: str,
        frame_index: int,
        frame_path: Path,
        frame_bytes: bytes,
        reason: str,
    ) -> Optional[dict]:
        if self.stopped():
            return None
        detect_chain_started_at = time.perf_counter()
        processed_bytes, _, preprocess_timings_ms = self.client.preprocess(frame_bytes)
        detect_chain_preprocess_ms = preprocess_timings_ms["chain_preprocess_total_ms"]
        if self.stopped():
            return None
        detection_response, detection_latency = self.client.detect(frame_path.name, processed_bytes)
        if self.stopped():
            return None
        best_detection = select_best_detection(detection_response.get("detections", []))
        if best_detection is None:
            raise RuntimeError(f"detection failed on {sequence_name}/{frame_path.name}")

        detection_score = float(best_detection.get("confidence", best_detection.get("score", 0.0)))
        if detection_score < self.detect_score_threshold:
            raise RuntimeError(
                f"detection score too low on {sequence_name}/{frame_path.name}: {detection_score:.4f}"
            )

        bbox_xyxy = parse_detection_bbox(best_detection)
        _, init_tracker_latency = self.client.init_tracker(frame_path.name, processed_bytes, bbox_xyxy)
        if self.stopped():
            return None
        detect_chain_total_ms = (time.perf_counter() - detect_chain_started_at) * 1000.0
        return self._build_detect_event(
            sequence_name=sequence_name,
            frame_index=frame_index,
            frame_name=frame_path.name,
            source_bytes=processed_bytes,
            detection_response=detection_response,
            detection_score=detection_score,
            bbox_xyxy=bbox_xyxy,
            reason=reason,
            latency_ms=detection_latency,
            chain_timings_ms={
                "detect_chain_preprocess_ms": detect_chain_preprocess_ms,
                "detect_chain_preprocess_quality_estimate_ms": preprocess_timings_ms["chain_preprocess_quality_estimate_ms"],
                "detect_chain_preprocess_apply_ms": preprocess_timings_ms["chain_preprocess_apply_ms"],
                "detect_chain_init_tracker_http_latency_ms": init_tracker_latency,
                "detect_chain_total_ms": detect_chain_total_ms,
            },
        )

    def iter_events(self):
        self.validate()
        tracker_initialized = False
        for sequence_index, sequence_name in enumerate(self.active_sequences):
            if self.stopped():
                return
            frames = load_sequence_frames(self.dataset_root, sequence_name, self.max_frames_per_sequence)
            if not frames:
                continue

            frame_plan = self._build_frame_plan(frames, sequence_index)
            if not frame_plan:
                continue

            if not tracker_initialized:
                if self.stopped():
                    return
                first_frame_index, first_frame, _ = frame_plan[0]
                first_bytes = first_frame.read_bytes()
                detect_event = self._detect_and_init(
                    sequence_name=sequence_name,
                    frame_index=first_frame_index,
                    frame_path=first_frame,
                    frame_bytes=first_bytes,
                    reason="init",
                )
                if detect_event is None or self.stopped():
                    return
                yield detect_event
                tracker_initialized = True
                frame_plan = frame_plan[1:]
                if not frame_plan:
                    continue
                if self._wait_or_stopped():
                    return

            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="track-frame-prepare") as prepare_executor:
                next_prepare_future: Optional[Future[PreparedFrame]] = self._submit_prepare_frame(
                    prepare_executor,
                    sequence_name,
                    frame_plan[0],
                )

                for frame_plan_index in range(len(frame_plan)):
                    if self.stopped():
                        return
                    if next_prepare_future is None:
                        return

                    prepare_wait_started_at = time.perf_counter()
                    prepared_frame = next_prepare_future.result()
                    prepare_wait_ms = (time.perf_counter() - prepare_wait_started_at) * 1000.0
                    prepare_overlap_saved_ms = max(prepared_frame.prepare_total_ms - prepare_wait_ms, 0.0)

                    next_frame_plan_index = frame_plan_index + 1
                    next_prepare_future = (
                        self._submit_prepare_frame(
                            prepare_executor,
                            sequence_name,
                            frame_plan[next_frame_plan_index],
                        )
                        if next_frame_plan_index < len(frame_plan)
                        else None
                    )

                    chain_preprocess_ms = prepared_frame.preprocess_timings_ms["chain_preprocess_total_ms"]
                    track_response, track_latency = self.client.track_prepared(
                        prepared_frame.frame_path.name,
                        prepared_frame.processed_bytes,
                        prepared_frame.raw_rgb_bytes,
                        prepared_frame.raw_width,
                        prepared_frame.raw_height,
                        prepared_frame.raw_prepare_ms,
                    )
                    if self.stopped():
                        return
                    track_event = self._build_track_event(
                        sequence_name=prepared_frame.sequence_name,
                        frame_index=prepared_frame.frame_index,
                        frame_name=prepared_frame.frame_path.name,
                        source_bytes=prepared_frame.processed_bytes,
                        track_response=track_response,
                        latency_ms=track_latency,
                        chain_timings_ms={
                            "track_chain_read_frame_ms": prepared_frame.read_frame_ms,
                            "track_chain_preprocess_ms": chain_preprocess_ms,
                            "track_chain_preprocess_quality_estimate_ms": prepared_frame.preprocess_timings_ms[
                                "chain_preprocess_quality_estimate_ms"
                            ],
                            "track_chain_preprocess_apply_ms": prepared_frame.preprocess_timings_ms[
                                "chain_preprocess_apply_ms"
                            ],
                            "track_chain_prepare_total_ms": prepared_frame.prepare_total_ms,
                            "track_chain_prepare_wait_ms": prepare_wait_ms,
                            "track_chain_prepare_overlap_saved_ms": prepare_overlap_saved_ms,
                        },
                        reason=prepared_frame.probe_reason,
                    )
                    yield track_event

                    if self.stopped():
                        return
                    should_redetect, detect_reason = self._should_redetect(
                        probe_reason=prepared_frame.probe_reason,
                        track_response=track_response,
                    )
                    if should_redetect:
                        if self.stopped():
                            return
                        detect_event = self._detect_and_init(
                            sequence_name=prepared_frame.sequence_name,
                            frame_index=prepared_frame.frame_index,
                            frame_path=prepared_frame.frame_path,
                            frame_bytes=prepared_frame.frame_bytes,
                            reason=detect_reason or "recover",
                        )
                        if detect_event is None or self.stopped():
                            return
                        yield detect_event

                    if self._wait_or_stopped():
                        return
