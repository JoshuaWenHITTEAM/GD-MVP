import os
from pathlib import Path


AGENTS_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = Path(__file__).resolve().parent
DATA_ROOT = BACKEND_ROOT / "data"
JOBS_ROOT = DATA_ROOT / "jobs"
STORE_PATH = DATA_ROOT / "job_store.json"

TASK_DEFAULT_CONFIGS = {
    "detect": AGENTS_ROOT / "DQNv2" / "configs" / "dqn_detection_train.yaml",
    "track": AGENTS_ROOT / "DQNv2" / "configs" / "dqn_tracking_train.yaml",
    "preprocess": AGENTS_ROOT / "DQNv2" / "configs" / "dqn_preprocess_train.yaml",
}

ALLOWED_OVERRIDE_KEYS = {
    "cuda",
    "torch_deterministic",
    "capture_video",
    "use_docker",
    "test_mode",
    "track",
    "wandb_project_name",
    "wandb_entity",
    "exp_name",
    "env_id",
    "modal",
    "seed",
    "total_timesteps",
    "learning_starts",
    "target_network_frequency",
    "train_frequency",
    "save_checkpoints_freq",
    "learning_rate",
    "batch_size",
    "eval_episodes",
    "num_layers",
    "buffer_size",
    "gamma",
    "tau",
    "start_e",
    "end_e",
    "exploration_fraction",
    "dataset_root",
    "results_root",
    "output_root",
    "split",
    "models",
}

CONDA_RUNNER = Path(os.environ.get("CONDA_EXE", "conda"))
CONDA_ENV_NAME = "GD-MVP"
