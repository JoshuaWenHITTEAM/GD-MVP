import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from decision_algorithm.algorithm_chain.minimal_runtime import (
        DEFAULT_DATASET_ROOT,
        DEFAULT_MID_SEQUENCE_PROBE_SCORE_THRESHOLD,
        DEFAULT_MID_SEQUENCE_SKIP_FRAMES,
        DEFAULT_SEQUENCES,
        DEFAULT_TRANSITION_SKIP_FRAMES,
        SCENARIO_SEQUENCE_TRANSITION,
        SUPPORTED_SCENARIOS,
        SimpleChainRunner,
    )
else:
    from decision_algorithm.algorithm_chain.minimal_runtime import (
        DEFAULT_DATASET_ROOT,
        DEFAULT_MID_SEQUENCE_PROBE_SCORE_THRESHOLD,
        DEFAULT_MID_SEQUENCE_SKIP_FRAMES,
        DEFAULT_SEQUENCES,
        DEFAULT_TRANSITION_SKIP_FRAMES,
        SCENARIO_SEQUENCE_TRANSITION,
        SUPPORTED_SCENARIOS,
        SimpleChainRunner,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a minimal detect+track chain on local sequences.")
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--scenario", choices=SUPPORTED_SCENARIOS, default=SCENARIO_SEQUENCE_TRANSITION)
    parser.add_argument("--sequences", nargs="+", default=list(DEFAULT_SEQUENCES))
    parser.add_argument("--max-frames-per-sequence", type=int, default=48)
    parser.add_argument("--track-score-threshold", type=float, default=0.15)
    parser.add_argument("--detect-score-threshold", type=float, default=0.2)
    parser.add_argument("--sequence-transition-score-threshold", type=float, default=0.45)
    parser.add_argument("--mid-sequence-probe-score-threshold", type=float, default=DEFAULT_MID_SEQUENCE_PROBE_SCORE_THRESHOLD)
    parser.add_argument("--mid-sequence-skip-frames", type=int, default=DEFAULT_MID_SEQUENCE_SKIP_FRAMES)
    parser.add_argument("--transition-skip-frames", type=int, default=DEFAULT_TRANSITION_SKIP_FRAMES)
    parser.add_argument("--frame-interval-s", type=float, default=0.0)
    parser.add_argument("--output", type=Path, default=None, help="optional json output path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runner = SimpleChainRunner(
        dataset_root=args.dataset_root,
        sequences=tuple(args.sequences),
        scenario=args.scenario,
        max_frames_per_sequence=args.max_frames_per_sequence,
        track_score_threshold=args.track_score_threshold,
        detect_score_threshold=args.detect_score_threshold,
        sequence_transition_score_threshold=args.sequence_transition_score_threshold,
        mid_sequence_probe_score_threshold=args.mid_sequence_probe_score_threshold,
        mid_sequence_skip_frames=args.mid_sequence_skip_frames,
        transition_skip_frames=args.transition_skip_frames,
        frame_interval_s=args.frame_interval_s,
    )
    try:
        events = list(runner.iter_events())
    finally:
        runner.close()

    summary = {
        "dataset_root": str(args.dataset_root),
        "scenario": args.scenario,
        "sequences": args.sequences,
        "event_count": len(events),
        "events": events,
    }
    if args.output is not None:
        args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
