from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


JobStatus = Literal["queued", "starting", "running", "completed", "failed", "stopped"]
TaskType = Literal["detect", "track", "preprocess"]


class TrainingCreateRequest(BaseModel):
    task_type: TaskType
    train_config: Dict[str, Any] = Field(default_factory=dict)


class ProgressSnapshot(BaseModel):
    current_step: int = 0
    total_steps: int = 0
    progress: float = 0.0
    gpu_util: Optional[float] = None
    gpu_mem: Optional[float] = None
    cpu_util: Optional[float] = None


class SummarySnapshot(BaseModel):
    latest_reward: Optional[float] = None
    latest_td_loss: Optional[float] = None
    latest_lr: Optional[float] = None
    latest_epsilon: Optional[float] = None
    latest_checkpoint: Optional[str] = None
    sps: Optional[int] = None


class RuntimeSnapshot(BaseModel):
    pid: Optional[int] = None
    run_dir: Optional[str] = None
    log_file: Optional[str] = None
    merged_config_path: Optional[str] = None


class JobResponse(BaseModel):
    job_id: str
    task_type: TaskType
    status: JobStatus
    created_at: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    progress: ProgressSnapshot
    summary: SummarySnapshot
    runtime: RuntimeSnapshot
    config: Dict[str, Any]
    error_message: Optional[str] = None


class JobListResponse(BaseModel):
    items: List[JobResponse]
    total: int
