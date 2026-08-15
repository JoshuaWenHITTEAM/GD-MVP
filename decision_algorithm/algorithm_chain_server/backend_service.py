import json
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from decision_algorithm.algorithm_chain_server.minimal_runtime import (
    SCENARIO_SEQUENCE_TRANSITION,
    SimpleChainRunner,
)

EVENT_LIVE_STREAM = "live_stream"
EVENT_APPEARANCE_DEMO = "appearance_demo"
EVENT_LIFECYCLE_DEMO = "lifecycle_demo"


class StreamRequest(BaseModel):
    event_type: str


def build_runner(event_type: str) -> SimpleChainRunner:
    if event_type in {EVENT_LIVE_STREAM, EVENT_APPEARANCE_DEMO, EVENT_LIFECYCLE_DEMO}:
        return SimpleChainRunner(
            scenario=SCENARIO_SEQUENCE_TRANSITION,
            max_frames_per_sequence=180,
        )

    raise ValueError(f"unsupported event_type: {event_type}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="Algorithm Chain Stream Backend", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "input_source": "shm",
        "supported_event_types": [EVENT_LIVE_STREAM, EVENT_APPEARANCE_DEMO, EVENT_LIFECYCLE_DEMO],
    }


@app.post("/api/stream")
def api_stream(req: StreamRequest):
    task_id = uuid.uuid4().hex

    def stream():
        runner = build_runner(req.event_type)
        try:
            yield f"data: {json.dumps({'task_id': task_id, 'event_type': req.event_type, 'stage': 'start'}, ensure_ascii=False)}\n\n"
            for event in runner.iter_events():
                payload = {
                    "task_id": task_id,
                    "event_type": req.event_type,
                    **event,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'task_id': task_id, 'event_type': req.event_type, 'stage': 'done'}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            payload = {
                "task_id": task_id,
                "event_type": req.event_type,
                "stage": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            runner.close()

    return StreamingResponse(stream(), media_type="text/event-stream")
