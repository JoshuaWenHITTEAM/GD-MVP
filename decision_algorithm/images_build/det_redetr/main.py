import argparse
from pathlib import Path

from ultralytics import RTDETR


ROOT = Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal RT-DETR inference entrypoint")
    parser.add_argument(
        "--model",
        default=str(ROOT / "models" / "anti_uav_rtdetr.pt"),
        help="Inference model weights",
    )
    parser.add_argument(
        "--source",
        default="https://ultralytics.com/images/bus.jpg",
        help="Image, folder, video, webcam, or URL",
    )
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--device", default="0", help="CUDA device id or cpu")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--project", default=str(ROOT / "output"), help="Output root")
    parser.add_argument("--name", default="predict", help="Run name")
    return parser


def predict(args: argparse.Namespace) -> None:
    model = RTDETR(args.model)
    model.predict(
        source=args.source,
        imgsz=args.imgsz,
        device=args.device,
        conf=args.conf,
        save=True,
        project=args.project,
        name=args.name,
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    predict(args)


if __name__ == "__main__":
    main()
