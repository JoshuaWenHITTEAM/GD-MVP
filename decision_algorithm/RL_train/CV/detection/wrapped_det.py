import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from PIL import Image


def compute_iou(box_a, box_b):
    x1 = max(float(box_a[0]), float(box_b[0]))
    y1 = max(float(box_a[1]), float(box_b[1]))
    x2 = min(float(box_a[2]), float(box_b[2]))
    y2 = min(float(box_a[3]), float(box_b[3]))

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, float(box_a[2]) - float(box_a[0])) * max(0.0, float(box_a[3]) - float(box_a[1]))
    area_b = max(0.0, float(box_b[2]) - float(box_b[0])) * max(0.0, float(box_b[3]) - float(box_b[1]))
    union = area_a + area_b - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


class DetQuest(gym.Env):
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
        super(DetQuest, self).__init__()
        if modal != "RGB":
            raise ValueError(f"DetQuest currently supports modal='RGB' only, got {modal}")
        if use_docker:
            raise ValueError("Pre-generated detection training requires use_docker=False")

        self.modal = modal
        self.use_docker = use_docker
        self.test_mode = test_mode
        self.split = split

        agents_root = Path(__file__).resolve().parents[2]
        self.dataset_root = Path(dataset_root or agents_root.parent / "anti-uav-det").resolve()
        self.results_root = Path(results_root or agents_root / "vis_res").resolve()
        self.output_root = Path(output_root or agents_root / "detection_outputs").resolve()

        raw_models = models or ["yolov8", "rtdetr"]
        if isinstance(raw_models, str):
            raw_models = [item.strip() for item in raw_models.split(",") if item.strip()]
        self.model_names = list(raw_models)
        if not self.model_names:
            raise ValueError("At least one detection model is required")

        self.img_path = self.dataset_root / self.split / "img"
        self.gt_path = self.dataset_root / self.split / "xml"
        if not self.img_path.exists():
            raise FileNotFoundError(f"Image directory does not exist: {self.img_path}")
        if not self.gt_path.exists():
            raise FileNotFoundError(f"Annotation directory does not exist: {self.gt_path}")

        self.results_path = self._build_results_path()
        self.output_vis = self.output_root / self.modal / "output_vis"
        self.output_txt = self.output_root / self.modal / "output_txt"
        self.output_txt_for_eval = self.output_root / self.modal / "output_txt_for_eval"
        for path in [self.output_vis, self.output_txt, self.output_txt_for_eval]:
            path.mkdir(parents=True, exist_ok=True)

        self.n_discrete_actions = len(self.model_names)
        self.n_channels = 3
        self.frame_width = 256
        self.frame_height = 256
        self.mean_vector = np.zeros((1, 1, 3), dtype=np.float32)
        self.std_vector = np.ones((1, 1, 3), dtype=np.float32)
        self.classes = ["UAV"]

        self.sequence = self._build_sequence()
        self.gt = [f"{Path(name).stem}.xml" for name in self.sequence]
        self.action_space = spaces.Discrete(self.n_discrete_actions)
        self.observation = np.zeros((self.n_channels, self.frame_width, self.frame_height), dtype=np.float32)
        self.observation_space = spaces.Box(
            low=0.0,
            high=255.0,
            shape=(self.n_channels, self.frame_width, self.frame_height),
            dtype=np.float32,
        )
        self.current_frame_index = 0
        self.step_count = 0
        self.cv_model = None
        self.iou_thres = 0.5

    def _build_results_path(self):
        result_paths = {}
        for model_name in self.model_names:
            if model_name == "yolov8":
                candidate = self.results_root / "yolov8" / self.split / "json"
            elif model_name == "rtdetr":
                candidate = self.results_root / "rtdetr" / self.split
            else:
                candidate = self.results_root / model_name / self.split
            if not candidate.exists():
                raise FileNotFoundError(f"Result directory does not exist for model '{model_name}': {candidate}")
            result_paths[model_name] = candidate
        return result_paths

    def _build_sequence(self):
        sequence = []
        for image_name in sorted(os.listdir(self.img_path)):
            stem = Path(image_name).stem
            if not image_name.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
                continue
            if not (self.gt_path / f"{stem}.xml").exists():
                continue
            sequence.append(image_name)
        if not sequence:
            raise ValueError(f"No valid image/xml pairs found under {self.dataset_root / self.split}")
        return sequence

    def step(self, action):
        model_list = list(self.results_path.keys())
        if not 0 <= action < self.n_discrete_actions:
            raise ValueError(f"Action {action} is out of range")
        self.cv_model = model_list[action]

        done = False
        if self.step_count == len(self.sequence) and self.test_mode:
            done = True
        if self.current_frame_index == (len(self.sequence) - 1):
            self.current_frame_index = -1

        reward = self.get_reward_conf(self.cv_model, self.current_frame_index)
        self.observation = self.state_preprocess(self.current_frame_index + 1)
        info = {
            "episode": {
                "a": action,
                "r": reward,
                "l": self.current_frame_index,
                "n": self.sequence[self.current_frame_index],
            },
        }

        self.current_frame_index += 1
        self.step_count += 1
        return self.observation, reward, done, False, info

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.current_frame_index = np.random.randint(0, len(self.sequence))
        self.step_count = 0
        self.observation = self.state_preprocess(self.current_frame_index)
        return self.observation, {}

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
        observation = observation.transpose(2, 0, 1).reshape(self.n_channels, self.frame_height, self.frame_width)
        return observation.astype(np.float32)

    def load_gt(self, index):
        xml_path = self.gt_path / f"{Path(self.sequence[index]).stem}.xml"
        tree = ET.parse(xml_path)
        root = tree.getroot()
        gt = []
        for obj in root.findall("object"):
            bbox = obj.find("bndbox")
            if bbox is None:
                continue
            gt.append(
                {
                    "class_id": 0,
                    "bbox": [
                        float(bbox.findtext("xmin", default="0")),
                        float(bbox.findtext("ymin", default="0")),
                        float(bbox.findtext("xmax", default="0")),
                        float(bbox.findtext("ymax", default="0")),
                    ],
                }
            )
        return gt

    def load_detections(self, model, index):
        json_path = self.results_path[model] / f"{Path(self.sequence[index]).stem}.json"
        if not json_path.exists():
            return []

        with open(json_path, "r", encoding="utf-8") as file:
            payload = json.load(file)

        raw_detections = payload.get("detections")
        if raw_detections is None:
            raw_detections = payload.get("predictions", [])

        detections = []
        for det in raw_detections:
            bbox = det.get("bbox_xyxy") or det.get("bbox")
            if bbox is None:
                continue
            detections.append(
                {
                    "class_id": int(det.get("class_id", 0)),
                    "score": float(det.get("score", 0.0)),
                    "bbox": [
                        float(bbox.get("x1", 0.0)),
                        float(bbox.get("y1", 0.0)),
                        float(bbox.get("x2", 0.0)),
                        float(bbox.get("y2", 0.0)),
                    ],
                }
            )
        return detections

    def get_reward_conf(self, model, index):
        gt = self.load_gt(index)
        dets = self.load_detections(model, index)
        return self.get_conf(gt, dets, len(self.classes), iou_thres=self.iou_thres)

    @staticmethod
    def get_conf(gt, dets, class_num, iou_thres=0.5):
        reward = 0.0
        for class_id in range(class_num):
            dets_c = [det for det in dets if int(det["class_id"]) == class_id]
            dets_c = sorted(dets_c, key=lambda det: float(det["score"]), reverse=True)
            gts_c = [g for g in gt if int(g["class_id"]) == class_id]

            tp = np.zeros(len(dets_c))
            fp = np.zeros(len(dets_c))
            matched = np.zeros(len(gts_c))

            for i, det in enumerate(dets_c):
                iou_max = 0.0
                jmax = -1
                for j, gt_item in enumerate(gts_c):
                    iou = compute_iou(det["bbox"], gt_item["bbox"])
                    if iou > iou_max:
                        iou_max = iou
                        jmax = j

                if iou_max >= iou_thres and jmax >= 0:
                    if matched[jmax] == 0:
                        tp[i] = 1
                        matched[jmax] = 1
                    else:
                        fp[i] = 1
                else:
                    fp[i] = 1

            idx_tp = [i for i, value in enumerate(tp) if int(value) == 1]
            idx_fp = [i for i, value in enumerate(fp) if int(value) == 1]
            idx_fn = [i for i, value in enumerate(matched) if int(value) == 0]

            if idx_tp:
                r_tp = sum(float(dets_c[i]["score"]) for i in idx_tp) / len(idx_tp)
            elif not idx_tp and gts_c:
                r_tp = -100.0
            else:
                r_tp = 0.0

            if idx_fp:
                r_fp = -sum(float(dets_c[i]["score"]) for i in idx_fp) / len(idx_fp)
            else:
                r_fp = 0.0

            reward += (r_tp + r_fp - len(idx_fn) * 0.75) * 100.0

        if reward == 0.0:
            reward = -10000.0
        return reward

    def __str__(self):
        return "DetQuestEnvironment"
