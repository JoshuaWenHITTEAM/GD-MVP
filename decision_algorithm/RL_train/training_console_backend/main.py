import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from .event_bus import EventBus
from .job_manager import JobManager
from .job_store import JobStore
from .schemas import JobListResponse, JobResponse, TrainingCreateRequest
from .utils import sse_message


store = JobStore()
event_bus = EventBus()
job_manager = JobManager(store=store, event_bus=event_bus)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="Training Console Backend", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/train/jobs", response_model=JobResponse)
async def create_job(request: TrainingCreateRequest) -> dict:
    try:
        return await job_manager.create_job(request.task_type, request.train_config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/train/jobs", response_model=JobListResponse)
async def list_jobs() -> dict:
    items = job_manager.list_jobs()
    return {"items": items, "total": len(items)}


@app.get("/api/train/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> dict:
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/train/jobs/{job_id}/stop", response_model=JobResponse)
async def stop_job(job_id: str) -> dict:
    try:
        job = await job_manager.stop_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    return job


@app.get("/api/train/jobs/{job_id}/stream")
async def stream_job(job_id: str) -> StreamingResponse:
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        current_job = job_manager.get_job(job_id)
        if current_job:
            yield sse_message(
                "status",
                {
                    "event": "status",
                    "job_id": job_id,
                    "timestamp": current_job["started_at"] or current_job["created_at"],
                    "payload": {
                        "status": current_job["status"],
                        "run_dir": current_job["runtime"]["run_dir"],
                    },
                },
            )
            yield sse_message(
                "progress",
                {
                    "event": "progress",
                    "job_id": job_id,
                    "timestamp": current_job["started_at"] or current_job["created_at"],
                    "payload": current_job["progress"],
                },
            )
            yield sse_message(
                "metrics",
                {
                    "event": "metrics",
                    "job_id": job_id,
                    "timestamp": current_job["started_at"] or current_job["created_at"],
                    "payload": {
                        "metric_source": "snapshot",
                        "step": current_job["progress"]["current_step"],
                        "reward": current_job["summary"]["latest_reward"],
                        "td_loss": current_job["summary"]["latest_td_loss"],
                        "epsilon": current_job["summary"]["latest_epsilon"],
                        "learning_rate": current_job["summary"]["latest_lr"],
                    },
                },
            )
            if current_job["status"] == "stopped":
                yield sse_message(
                    "stopped",
                    {
                        "event": "stopped",
                        "job_id": job_id,
                        "timestamp": current_job["ended_at"] or current_job["started_at"] or current_job["created_at"],
                        "payload": {"status": "stopped"},
                    },
                )
                return
            if current_job["status"] in {"completed", "failed"}:
                return

        async for event in event_bus.stream(job_id):
            yield sse_message(event["event"], event)
            if event["event"] in {"completed", "failed", "stopped"}:
                await asyncio.sleep(0)
                return

    return StreamingResponse(event_generator(), media_type="text/event-stream")
