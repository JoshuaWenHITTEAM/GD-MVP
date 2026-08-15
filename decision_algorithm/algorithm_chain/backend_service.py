import json
import threading
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from decision_algorithm.algorithm_chain.minimal_runtime import (
    DEFAULT_DATASET_ROOT,
    DEFAULT_MID_SEQUENCE_PROBE_SCORE_THRESHOLD,
    DEFAULT_MID_SEQUENCE_SKIP_FRAMES,
    DEFAULT_SEQUENCES,
    DEFAULT_TRANSITION_SKIP_FRAMES,
    SCENARIO_MID_GAP,
    SCENARIO_SEQUENCE_TRANSITION,
    SimpleChainRunner,
)


class StreamRequest(BaseModel):
    event_type: str


_ACTIVE_RUNNERS: dict[str, SimpleChainRunner] = {}
_ACTIVE_RUNNERS_LOCK = threading.Lock()
_LATEST_FRAMES: dict[str, tuple[bytes, str, int | None]] = {}
_LATEST_FRAMES_LOCK = threading.Lock()


def build_runner(event_type: str, stop_event: threading.Event) -> SimpleChainRunner:
    if event_type == SCENARIO_MID_GAP:
        return SimpleChainRunner(
            dataset_root=DEFAULT_DATASET_ROOT,
            sequences=(DEFAULT_SEQUENCES[0],),
            scenario=SCENARIO_MID_GAP,
            max_frames_per_sequence=240,
            mid_sequence_probe_score_threshold=DEFAULT_MID_SEQUENCE_PROBE_SCORE_THRESHOLD,
            mid_sequence_skip_frames=DEFAULT_MID_SEQUENCE_SKIP_FRAMES,
            stop_event=stop_event,
        )

    if event_type == SCENARIO_SEQUENCE_TRANSITION:
        return SimpleChainRunner(
            dataset_root=DEFAULT_DATASET_ROOT,
            sequences=DEFAULT_SEQUENCES,
            scenario=SCENARIO_SEQUENCE_TRANSITION,
            max_frames_per_sequence=240,
            mid_sequence_probe_score_threshold=DEFAULT_MID_SEQUENCE_PROBE_SCORE_THRESHOLD,
            transition_skip_frames=DEFAULT_TRANSITION_SKIP_FRAMES,
            stop_event=stop_event,
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
        "dataset_root": str(DEFAULT_DATASET_ROOT),
        "supported_event_types": [SCENARIO_MID_GAP, SCENARIO_SEQUENCE_TRANSITION],
    }


@app.post("/api/stream")
def api_stream(req: StreamRequest):
    task_id = uuid.uuid4().hex
    stop_event = threading.Event()

    def stream():
        runner = build_runner(req.event_type, stop_event)
        with _ACTIVE_RUNNERS_LOCK:
            _ACTIVE_RUNNERS[task_id] = runner
        try:
            yield f"data: {json.dumps({'task_id': task_id, 'event_type': req.event_type, 'stage': 'start'}, ensure_ascii=False)}\n\n"
            for event in runner.iter_events():
                if runner.stopped():
                    break
                image_bytes = event.pop("_image_bytes", None)
                image_media_type = event.pop("_image_media_type", "image/jpeg")
                if isinstance(image_bytes, bytes):
                    with _LATEST_FRAMES_LOCK:
                        _LATEST_FRAMES[task_id] = (
                            image_bytes,
                            str(image_media_type),
                            event.get("frame_index") if isinstance(event.get("frame_index"), int) else None,
                        )
                payload = {
                    "task_id": task_id,
                    "event_type": req.event_type,
                    **event,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            stage = "stopped" if runner.stopped() else "done"
            yield f"data: {json.dumps({'task_id': task_id, 'event_type': req.event_type, 'stage': stage}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            if runner.stopped():
                payload = {
                    "task_id": task_id,
                    "event_type": req.event_type,
                    "stage": "stopped",
                }
            else:
                payload = {
                    "task_id": task_id,
                    "event_type": req.event_type,
                    "stage": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            runner.stop()
            runner.close()
            with _ACTIVE_RUNNERS_LOCK:
                _ACTIVE_RUNNERS.pop(task_id, None)
            with _LATEST_FRAMES_LOCK:
                _LATEST_FRAMES.pop(task_id, None)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/frame/{task_id}/latest")
def latest_frame(task_id: str):
    with _LATEST_FRAMES_LOCK:
        item = _LATEST_FRAMES.get(task_id)
    if item is None:
        raise HTTPException(status_code=404, detail="latest frame not found")
    image_bytes, media_type, frame_index = item
    headers = {
        "Cache-Control": "no-store",
    }
    if frame_index is not None:
        headers["X-Frame-Index"] = str(frame_index)
    return Response(content=image_bytes, media_type=media_type, headers=headers)


@app.post("/api/stop")
def stop_active_streams():
    with _ACTIVE_RUNNERS_LOCK:
        runners = list(_ACTIVE_RUNNERS.values())
    for runner in runners:
        runner.stop()
    return {"status": "stopping", "count": len(runners)}


@app.post("/api/stop/{task_id}")
def stop_stream(task_id: str):
    with _ACTIVE_RUNNERS_LOCK:
        runner = _ACTIVE_RUNNERS.get(task_id)
    if runner is None:
        return {"status": "not_found", "task_id": task_id}
    runner.stop()
    return {"status": "stopping", "task_id": task_id}
