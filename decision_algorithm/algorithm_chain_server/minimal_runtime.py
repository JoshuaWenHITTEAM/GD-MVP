import base64
import io
import time
from dataclasses import dataclass
from typing import Optional

import requests
from PIL import Image

from decision_algorithm.algorithm_chain_server.middle_obj.rdma_image_reader import IMAGE_READ_ERROR, get_image


SCENARIO_MID_GAP = "mid_gap"
SCENARIO_SEQUENCE_TRANSITION = "sequence_transition"
SUPPORTED_SCENARIOS = (SCENARIO_MID_GAP, SCENARIO_SEQUENCE_TRANSITION)
LIVE_SEQUENCE_NAME = "rdma_live"


@dataclass(frozen=True)
class DetectorConfig:
    name: str
    base_url: str
    model_name: str


@dataclass(frozen=True)
class TrackerConfig:
    name: str
    base_url: str


DEFAULT_DETECTOR = DetectorConfig(
    name="yolov8",
    base_url="http://127.0.0.1:9000",
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


def null_result_event_payload(image_bytes: bytes) -> tuple[str, str]:
    return encode_image_bytes(image_bytes), "image/jpeg"


def grayscale_image_to_jpeg_bytes(image) -> bytes:
    if image.ndim != 2:
        raise ValueError(f"expected 2D grayscale image, got shape={getattr(image, 'shape', None)}")
    pil_image = Image.fromarray(image.astype("uint8"), mode="L").convert("RGB")
    buf = io.BytesIO()
    pil_image.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


class ServiceClient:
    def __init__(self, detector: DetectorConfig, tracker: TrackerConfig):
        self.detector = detector
        self.tracker = tracker
        self._sessions: dict[str, requests.Session] = {}

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
                "return_image": "true",
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

    def track(self, frame_name: str, image_bytes: bytes) -> tuple[dict, float]:
        return self._post_image(
            self.tracker.base_url,
            "/track/file",
            frame_name,
            image_bytes,
            {"return_image": "true"},
        )
    def output():
        return bbox


class SimpleChainRunner:
    def __init__(
        self,
        *,
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
    ):
        if scenario not in SUPPORTED_SCENARIOS:
            raise ValueError(f"unsupported scenario: {scenario}")
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
        self.client = ServiceClient(detector=detector, tracker=tracker)

    def close(self) -> None:
        self.client.close()

    def validate(self) -> None:
        self.client.check_ready()

    def _build_detect_event(
        self,
        *,
        sequence_name: str,
        frame_index: int,
        frame_name: str,
        source_bytes: bytes,
        detection_response: Optional[dict],
        detection_score: Optional[float],
        bbox_xyxy: Optional[list[int]],
        reason: str,
        latency_ms: float,
    ) -> dict:
        annotated = None
        media_type = "image/jpeg"
        if detection_response is not None:
            annotated = detection_response.get("annotated_image_base64")
            media_type = detection_response.get("annotated_media_type", "image/jpeg")
        image_base64, fallback_media_type = null_result_event_payload(source_bytes)
        result = None
        if bbox_xyxy is not None and detection_score is not None:
            result = {
                "detector": self.client.detector.name,
                "bbox_xyxy": bbox_xyxy,
                "score": round(float(detection_score), 6),
                "num_detections": int(detection_response.get("num_detections", 0)) if detection_response else 0,
                "latency_ms": round(latency_ms, 3),
            }
        return {
            "stage": "detect",
            "sequence": sequence_name,
            "frame_index": frame_index,
            "frame_name": frame_name,
            "reason": reason,
            "image_base64": annotated or image_base64,
            "image_media_type": media_type if annotated else fallback_media_type,
            "result": result,
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
        reason: Optional[str] = None,
    ) -> dict:
        tracked = track_response.get("tracked_image_base64")
        return {
            "stage": "track",
            "sequence": sequence_name,
            "frame_index": frame_index,
            "frame_name": frame_name,
            "reason": reason,
            "image_base64": tracked or encode_image_bytes(source_bytes),
            "image_media_type": track_response.get("tracked_media_type", "image/jpeg"),
            "result": {
                "tracker": self.client.tracker.name,
                "bbox_xyxy": [int(round(float(item))) for item in track_response["bbox_xyxy"]],
                "score": round(float(track_response["score"]), 6),
                "cache_version": int(track_response["cache_version"]),
                "latency_ms": round(latency_ms, 3),
            },
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

    def _detect_once(
        self,
        *,
        sequence_name: str,
        frame_index: int,
        frame_name: str,
        frame_bytes: bytes,
        reason_if_found: str,
        reason_if_missing: str,
    ) -> tuple[bool, dict]:
        detection_response, detection_latency = self.client.detect(frame_name, frame_bytes)
        best_detection = select_best_detection(detection_response.get("detections", []))
        if best_detection is None:
            return False, self._build_detect_event(
                sequence_name=sequence_name,
                frame_index=frame_index,
                frame_name=frame_name,
                source_bytes=frame_bytes,
                detection_response=detection_response,
                detection_score=None,
                bbox_xyxy=None,
                reason=reason_if_missing,
                latency_ms=detection_latency,
            )

        detection_score = float(best_detection.get("confidence", best_detection.get("score", 0.0)))
        if detection_score < self.detect_score_threshold:
            return False, self._build_detect_event(
                sequence_name=sequence_name,
                frame_index=frame_index,
                frame_name=frame_name,
                source_bytes=frame_bytes,
                detection_response=detection_response,
                detection_score=None,
                bbox_xyxy=None,
                reason=reason_if_missing,
                latency_ms=detection_latency,
            )

        bbox_xyxy = parse_detection_bbox(best_detection)
        self.client.init_tracker(frame_name, frame_bytes, bbox_xyxy)
        return True, self._build_detect_event(
            sequence_name=sequence_name,
            frame_index=frame_index,
            frame_name=frame_name,
            source_bytes=frame_bytes,
            detection_response=detection_response,
            detection_score=detection_score,
            bbox_xyxy=bbox_xyxy,
            reason=reason_if_found,
            latency_ms=detection_latency,
        )

    def iter_events(self):
        yield from self.iter_live_events()

    def iter_live_events(self):
        self.validate()
        tracker_initialized = False
        frame_index = 0
        while True:
            image = get_image()
            if isinstance(image, int) and image == IMAGE_READ_ERROR:
                time.sleep(0.01)
                continue

            frame_bytes = grayscale_image_to_jpeg_bytes(image)
            frame_name = f"frame_{frame_index:08d}.jpg"

            if not tracker_initialized:
                found, event = self._detect_once(
                    sequence_name=LIVE_SEQUENCE_NAME,
                    frame_index=frame_index,
                    frame_name=frame_name,
                    frame_bytes=frame_bytes,
                    reason_if_found="target_appeared",
                    reason_if_missing="no_target",
                )
                tracker_initialized = found
                yield event
            else:
                track_response, track_latency = self.client.track(frame_name, frame_bytes)
                should_redetect, detect_reason = self._should_redetect(
                    probe_reason=None,
                    track_response=track_response,
                )
                if not should_redetect:
                    yield self._build_track_event(
                        sequence_name=LIVE_SEQUENCE_NAME,
                        frame_index=frame_index,
                        frame_name=frame_name,
                        source_bytes=frame_bytes,
                        track_response=track_response,
                        latency_ms=track_latency,
                        reason=None,
                    )
                else:
                    found, event = self._detect_once(
                        sequence_name=LIVE_SEQUENCE_NAME,
                        frame_index=frame_index,
                        frame_name=frame_name,
                        frame_bytes=frame_bytes,
                        reason_if_found=detect_reason or "recover",
                        reason_if_missing="no_target_after_track_loss",
                    )
                    tracker_initialized = found
                    yield event

            frame_index += 1
            if self.frame_interval_s > 0:
                time.sleep(self.frame_interval_s)
