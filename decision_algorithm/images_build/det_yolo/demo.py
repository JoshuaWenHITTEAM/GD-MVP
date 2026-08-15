from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Optional

import cv2
import numpy as np

from detect import detect, detect_video


def draw_detections(frame: np.ndarray, detections: Iterable[dict]) -> np.ndarray:
    canvas = frame.copy()
    for item in detections:
        bbox = item["bbox"]
        x_center = int(bbox["x"])
        y_center = int(bbox["y"])
        width = int(bbox["w"])
        height = int(bbox["h"])
        x1 = max(x_center - width // 2, 0)
        y1 = max(y_center - height // 2, 0)
        x2 = min(x_center + width // 2, canvas.shape[1] - 1)
        y2 = min(y_center + height // 2, canvas.shape[0] - 1)
        label = f'{item["class"]}:{item["score"]:.2f}'
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 215, 255), 2)
        cv2.putText(
            canvas,
            label,
            (x1, max(y1 - 8, 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 215, 255),
            2,
            cv2.LINE_AA,
        )
    return canvas


def build_fallback_demo_frame() -> np.ndarray:
    frame = np.zeros((640, 960, 3), dtype=np.uint8)
    frame[:] = (24, 24, 24)
    cv2.putText(
        frame,
        "Anti-drone detection smoke test",
        (40, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.circle(frame, (730, 180), 16, (0, 215, 255), -1)
    cv2.line(frame, (710, 180), (750, 180), (0, 215, 255), 2)
    cv2.line(frame, (730, 160), (730, 200), (0, 215, 255), 2)
    return frame


def run_image_demo(
    input_path: Optional[str],
    output_path: Optional[str],
    conf_threshold: float,
    show: bool,
) -> List[dict]:
    if input_path:
        frame = cv2.imread(input_path)
        if frame is None:
            raise ValueError(f"Unable to load image: {input_path}")
    else:
        frame = build_fallback_demo_frame()

    detections = detect(frame if input_path is None else input_path, conf_threshold=conf_threshold)
    vis_frame = draw_detections(frame, detections)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(output_path, vis_frame)

    if show:
        cv2.imshow("detect-demo", vis_frame)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return detections


def run_video_demo(
    input_path: str,
    output_path: Optional[str],
    conf_threshold: float,
    show: bool,
    frame_stride: int,
) -> None:
    capture = cv2.VideoCapture(input_path)
    if not capture.isOpened():
        raise ValueError(f"Unable to open video: {input_path}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    writer = None
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            output_path,
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, height),
        )

    try:
        for result in detect_video(
            capture,
            conf_threshold=conf_threshold,
            frame_stride=frame_stride,
        ):
            frame = result["frame"]
            vis_frame = draw_detections(frame, result["detections"])
            if writer is not None:
                writer.write(vis_frame)
            if show:
                cv2.imshow("detect-demo", vis_frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        capture.release()
        if writer is not None:
            writer.release()
        if show:
            cv2.destroyAllWindows()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YOLO anti-drone detection demo")
    parser.add_argument("--input", type=str, default=None, help="Image or video path. If omitted, a synthetic smoke-test frame is used.")
    parser.add_argument("--output", type=str, default="output/demo_result.jpg", help="Output image or video path.")
    parser.add_argument("--conf", type=float, default=0.35, help="Confidence threshold.")
    parser.add_argument("--frame-stride", type=int, default=1, help="Process every N-th frame for video sources.")
    parser.add_argument("--show", dest="show", action="store_true", help="Show visualization in a local window.")
    parser.add_argument("--no-show", dest="show", action="store_false", help="Disable visualization window.")
    parser.set_defaults(show=False)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = args.input
    if input_path and Path(input_path).suffix.lower() in {".mp4", ".avi", ".mov", ".mkv"}:
        run_video_demo(
            input_path=input_path,
            output_path=args.output,
            conf_threshold=args.conf,
            show=args.show,
            frame_stride=args.frame_stride,
        )
        return

    detections = run_image_demo(
        input_path=input_path,
        output_path=args.output,
        conf_threshold=args.conf,
        show=args.show,
    )
    print({"detections": detections, "output": args.output})


if __name__ == "__main__":
    main()
