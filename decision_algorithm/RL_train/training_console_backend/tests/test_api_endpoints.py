import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

import training_console_backend.main as main_module
from training_console_backend.main import create_job, get_job, list_jobs, stop_job, stream_job
from training_console_backend.schemas import TrainingCreateRequest


SAMPLE_JOB = {
    "job_id": "job_test_001",
    "task_type": "detect",
    "status": "running",
    "created_at": "2026-04-16T00:00:00+00:00",
    "started_at": "2026-04-16T00:00:01+00:00",
    "ended_at": None,
    "progress": {
        "current_step": 20,
        "total_steps": 100,
        "progress": 0.2,
        "gpu_util": 12.0,
        "gpu_mem": 1024.0,
        "cpu_util": 18.0,
    },
    "summary": {
        "latest_reward": 66.6,
        "latest_td_loss": 0.123,
        "latest_lr": 1e-4,
        "latest_epsilon": 0.25,
        "latest_checkpoint": "/tmp/checkpoint.pth",
        "sps": 12,
    },
    "runtime": {
        "pid": 12345,
        "run_dir": "/tmp/run_dir",
        "log_file": "/tmp/run_dir/log.txt",
        "merged_config_path": "/tmp/run_dir/merged_config.yaml",
    },
    "config": {
        "total_timesteps": 100,
        "learning_rate": 1e-4,
    },
    "error_message": None,
}


async def _event_stream():
    yield {
        "event": "checkpoint",
        "job_id": "job_test_001",
        "timestamp": "2026-04-16T00:00:10+00:00",
        "payload": {"global_step": 20, "checkpoint_path": "/tmp/checkpoint.pth"},
    }
    yield {
        "event": "completed",
        "job_id": "job_test_001",
        "timestamp": "2026-04-16T00:00:11+00:00",
        "payload": {"status": "completed"},
    }


class ApiEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_job_success(self):
        request = TrainingCreateRequest(task_type="detect", train_config={"total_timesteps": 100})
        with patch("training_console_backend.main.job_manager.create_job", new=AsyncMock(return_value=SAMPLE_JOB)):
            response = await create_job(request)
        self.assertEqual(response["job_id"], "job_test_001")
        self.assertEqual(response["task_type"], "detect")

    async def test_create_job_invalid_config(self):
        request = TrainingCreateRequest(task_type="detect", train_config={"unknown": 1})
        with patch("training_console_backend.main.job_manager.create_job", new=AsyncMock(side_effect=ValueError("bad config"))):
            with self.assertRaises(HTTPException) as ctx:
                await create_job(request)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "bad config")

    async def test_list_jobs(self):
        with patch("training_console_backend.main.job_manager.list_jobs", new=Mock(return_value=[SAMPLE_JOB])):
            response = await list_jobs()
        self.assertEqual(response["total"], 1)
        self.assertEqual(response["items"][0]["job_id"], "job_test_001")

    async def test_get_job_success(self):
        with patch("training_console_backend.main.job_manager.get_job", new=Mock(return_value=SAMPLE_JOB)):
            response = await get_job("job_test_001")
        self.assertEqual(response["job_id"], "job_test_001")

    async def test_get_job_not_found(self):
        with patch("training_console_backend.main.job_manager.get_job", new=Mock(return_value=None)):
            with self.assertRaises(HTTPException) as ctx:
                await get_job("missing")
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_stop_job_success(self):
        stopped_job = dict(SAMPLE_JOB)
        stopped_job["status"] = "stopped"
        with patch("training_console_backend.main.job_manager.stop_job", new=AsyncMock(return_value=stopped_job)):
            response = await stop_job("job_test_001")
        self.assertEqual(response["status"], "stopped")

    async def test_stop_job_not_found(self):
        with patch("training_console_backend.main.job_manager.stop_job", new=AsyncMock(side_effect=KeyError("missing"))):
            with self.assertRaises(HTTPException) as ctx:
                await stop_job("missing")
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_stream_job_contains_checkpoint_event(self):
        fake_event_bus = Mock()
        fake_event_bus.stream = Mock(return_value=_event_stream())
        chunks = []
        with patch("training_console_backend.main.job_manager.get_job", new=Mock(return_value=SAMPLE_JOB)), \
             patch.object(main_module, "event_bus", fake_event_bus):
            response = await stream_job("job_test_001")
            iterator = response.body_iterator.__aiter__()
            for _ in range(5):
                chunk = await asyncio.wait_for(iterator.__anext__(), timeout=2)
                chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)

        merged = "".join(chunks)
        self.assertIn("event: status", merged)
        self.assertIn("event: progress", merged)
        self.assertIn("event: metrics", merged)
        self.assertIn("event: checkpoint", merged)
        self.assertIn("event: completed", merged)


if __name__ == "__main__":
    unittest.main()
