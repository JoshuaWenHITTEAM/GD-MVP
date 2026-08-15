import httpx

class JobService:
    def __init__(self):
        # 后端端口号应与实际后端服务一致
        self.base_url = "http://127.0.0.1:30000/api"

    async def get_history(self):
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/train/jobs")
            return resp.json()

    async def create_job(self, task_type: str, config: dict):
        train_config = {
            "exp_name": config.get("exp_name") or f"web_{task_type}_train",
            **config,
        }
        payload = {
            "task_type": task_type,
            "train_config": train_config,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/train/jobs", json=payload)
            if resp.status_code != 200 and resp.status_code != 201:
                raise Exception(f"后端返回错误: {resp.status_code}, 内容: {resp.text}")
            return resp.json()

    async def stop_job(self, job_id: str):
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/train/jobs/{job_id}/stop")
            return resp.json()

    async def get_job_detail(self, job_id: str):
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/train/jobs/{job_id}")
            return resp.json()

job_service = JobService()
