import random
from pathlib import Path

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from PIL import Image


def parse_bbox_line(line):
    cleaned = line.replace(",", " ").replace("\t", " ").strip()
    if not cleaned:
        return None
    parts = [part for part in cleaned.split() if part]
    if len(parts) < 4:
        return np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    try:
        values = [float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])]
    except ValueError:
        return np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    return np.array(values, dtype=np.float32)


def load_bbox_series(file_path):
    series = []
    with open(file_path, "r", encoding="utf-8") as handle:
        for line in handle:
            bbox = parse_bbox_line(line)
            if bbox is not None:
                series.append(bbox)
    return np.asarray(series, dtype=np.float32)


def calculate_iou(bbox1, bbox2):
    x1, y1, w1, h1 = bbox1
    x2, y2, w2, h2 = bbox2

    inter_x1 = max(x1, x2)
    inter_y1 = max(y1, y2)
    inter_x2 = min(x1 + w1, x2 + w2)
    inter_y2 = min(y1 + h1, y2 + h2)

    inter_area = max(0.0, inter_x2 - inter_x1) * max(0.0, inter_y2 - inter_y1)
    bbox1_area = max(0.0, w1) * max(0.0, h1)
    bbox2_area = max(0.0, w2) * max(0.0, h2)
    return inter_area / (bbox1_area + bbox2_area - inter_area + 1e-6)


def calculate_center_error(bbox1, bbox2):
    x1, y1, w1, h1 = bbox1
    x2, y2, w2, h2 = bbox2
    center1 = np.array([x1 + w1 / 2.0, y1 + h1 / 2.0], dtype=np.float32)
    center2 = np.array([x2 + w2 / 2.0, y2 + h2 / 2.0], dtype=np.float32)
    return float(np.linalg.norm(center1 - center2))


def evaluate_tracking_by_iou_and_ce(groundtruth, prediction):
    total_iou = 0.0
    total_center_error = 0.0
    valid_frames = 0

    for gt_bbox, pred_bbox in zip(groundtruth, prediction):
        if np.all(gt_bbox == 0):
            continue
        total_iou += calculate_iou(gt_bbox, pred_bbox)
        total_center_error += calculate_center_error(gt_bbox, pred_bbox)
        valid_frames += 1

    if valid_frames == 0:
        return 0.0, 0.0
    return total_iou / valid_frames, total_center_error / valid_frames


class TrackQuest(gym.Env):
    metadata = {"render.modes": ["human"]}

    def __init__(
        self,
        modal,
        use_docker,
        test_mode=False,
        dataset_root=None,
        results_root=None,
        split="test",
        models=None,
        output_root=None,
    ):
        super(TrackQuest, self).__init__()
        if modal != "IR":
            raise ValueError(f"TrackQuest currently supports modal='IR' only, got {modal}")
        if use_docker:
            raise ValueError("Pre-generated tracking training requires use_docker=False")

        self.modal = modal
        self.use_docker = use_docker
        self.test_mode = test_mode
        self.split = split

        agents_root = Path(__file__).resolve().parents[2]
        self.dataset_root = Path(dataset_root or agents_root.parent / "Anti-UAV-Tracking-V0").resolve()
        self.results_root = Path(results_root or agents_root / "vis_res").resolve()
        self.output_root = Path(output_root or agents_root / "tracking_outputs").resolve()

        raw_models = models or ["siamRPN++", "AVtrack"]
        if isinstance(raw_models, str):
            raw_models = [item.strip() for item in raw_models.split(",") if item.strip()]
        self.model_names = list(raw_models)
        if not self.model_names:
            raise ValueError("At least one tracking model is required")

        self.video_root = self.dataset_root / "Anti-UAV-Tracking-V0"
        self.gt_root = self.dataset_root / "Anti-UAV-Tracking-V0GT"
        if not self.video_root.exists():
            raise FileNotFoundError(f"Tracking video root does not exist: {self.video_root}")
        if not self.gt_root.exists():
            raise FileNotFoundError(f"Tracking gt root does not exist: {self.gt_root}")

        self.results_path = self._build_results_path()
        self.output_vis = self.output_root / self.modal / "output_vis"
        self.output_txt = self.output_root / self.modal / "output_txt"
        self.output_txt_for_eval = self.output_root / self.modal / "output_txt_for_eval"
        for path in [self.output_vis, self.output_txt, self.output_txt_for_eval]:
            path.mkdir(parents=True, exist_ok=True)

        self.sequences = self._discover_sequences()
        self.seq_name = None
        self.img_path = None
        self.gt_path = None
        self.sequence = None
        self.gt = None

        self.n_discrete_actions = len(self.model_names)
        self.n_channels = 3
        self.frame_width = 256
        self.frame_height = 256
        self.mean_vector = np.asarray([0.355, 0.355, 0.355], dtype=np.float32).reshape(1, 1, 3)
        self.std_vector = np.asarray([0.209, 0.209, 0.209], dtype=np.float32).reshape(1, 1, 3)

        self.action_space = spaces.Discrete(self.n_discrete_actions)
        self.observation = np.zeros((self.n_channels, self.frame_width, self.frame_height), dtype=np.float32)
        self.observation_space = spaces.Box(
            low=0.0,
            high=255.0,
            shape=(self.n_channels, self.frame_width, self.frame_height),
            dtype=np.float32,
        )

        self.current_frame_index = 1
        self.step_count = 0
        self.cv_model = None

    def _build_results_path(self):
        mapping = {}
        alias_map = {
            "siamrpn++": "siamRPN++",
            "siamRPN++": "siamRPN++",
            "avtrack": "AVtrack",
            "AVtrack": "AVtrack",
        }
        for model_name in self.model_names:
            normalized = alias_map.get(model_name, model_name)
            candidate = self.results_root / normalized
            if not candidate.exists():
                raise FileNotFoundError(f"Tracking result directory does not exist for model '{model_name}': {candidate}")
            mapping[model_name] = candidate
        return mapping

    def _discover_sequences(self):
        sequences = []
        for seq_dir in sorted(self.video_root.iterdir()):
            if not seq_dir.is_dir():
                continue
            gt_file = self.gt_root / f"{seq_dir.name}_gt.txt"
            if gt_file.exists():
                sequences.append(seq_dir.name)
        if not sequences:
            raise ValueError(f"No valid tracking sequences found under {self.video_root}")
        return sequences

    def _load_sequence(self, seq_name):
        img_path = self.video_root / seq_name
        gt_path = self.gt_root / f"{seq_name}_gt.txt"
        frame_names = sorted(
            [
                item.name
                for item in img_path.iterdir()
                if item.is_file() and item.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
            ]
        )
        gt = load_bbox_series(gt_path)
        if len(frame_names) < 2:
            raise ValueError(f"Sequence '{seq_name}' must contain at least 2 frames")
        if len(gt) < len(frame_names):
            raise ValueError(f"GT length is shorter than frame count for '{seq_name}'")
        self.seq_name = seq_name
        self.img_path = img_path
        self.gt_path = gt_path
        self.sequence = frame_names
        self.gt = gt[: len(frame_names)]

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        seq_pool = list(self.sequences)
        if self.seq_name in seq_pool and len(seq_pool) > 1:
            seq_pool.remove(self.seq_name)
        self._load_sequence(random.choice(seq_pool))
        self.current_frame_index = 1
        self.step_count = 0
        self.observation = self.state_preprocess(self.current_frame_index)
        return self.observation, {}

    def step(self, action):
        model_list = list(self.results_path.keys())
        if not 0 <= action < self.n_discrete_actions:
            raise ValueError(f"Action {action} is out of range")
        self.cv_model = model_list[action]

        reward = self.get_reward(self.cv_model, self.current_frame_index)
        done = False

        info = {
            "episode": {
                "a": action,
                "r": reward,
                "l": self.current_frame_index,
                "n": f"{self.seq_name}/{self.sequence[self.current_frame_index]}",
            },
        }

        if self.current_frame_index >= len(self.sequence) - 1:
            self.reset()
        else:
            self.current_frame_index += 1
            self.observation = self.state_preprocess(self.current_frame_index)

        self.step_count += 1
        return self.observation, reward, done, False, info

    def render(self):
        pass

    def close(self):
        pass

    @staticmethod
    def seed(seed):
        np.random.seed(seed)

    def state_preprocess(self, index):
        current_frame_path = self.img_path / self.sequence[index]
        image = Image.open(current_frame_path).convert("RGB")
        image = image.resize((self.frame_height, self.frame_width))
        observation = np.asarray(image, dtype=np.float32)
        observation = (observation / 255.0 - self.mean_vector) / self.std_vector
        observation = observation.transpose(2, 0, 1).reshape(self.n_channels, self.frame_width, self.frame_height)
        return observation.astype(np.float32)

    def load_prediction(self, model, index):
        result_file = self.results_path[model] / f"{self.seq_name}.txt"
        if not result_file.exists():
            raise FileNotFoundError(f"Tracking result file does not exist: {result_file}")

        series = load_bbox_series(result_file)
        pred_index = index - 1
        if pred_index < 0 or pred_index >= len(series):
            raise IndexError(f"Prediction index {pred_index} out of range for {result_file}")
        return series[pred_index]

    def get_reward(self, model, index):
        gt = [self.gt[index]]
        track_res = [self.load_prediction(model, index)]
        iou, ce = evaluate_tracking_by_iou_and_ce(gt, track_res)
        return float(iou - np.exp(-ce))
