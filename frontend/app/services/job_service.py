import httpx
import json

class JobService:
    def __init__(self):
        # 后端端口号应与实际后端服务一致
        self.base_url = "http://127.0.0.1:8000/api"

    async def get_history(self):
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/train/jobs")
            return resp.json()

    async def create_job(self, task_type: str, config: dict):
        # 构造后端要求的 Payload
        payload = {
            "task_type": task_type,
            "train_config": {
                "exp_name": f"web_{task_type}_demo",
                "learning_rate": float(config.get("learning_rate", 0.0001)),
                "start_e": float(config.get("epsilon", 1.0)),
                # 其他参数后端若有默认值可不传，或在此补全
                "cuda": True,
                "total_timesteps": 400
            }
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/train/jobs", json=payload)
             # --- 调试代码 ---
            print(f"请求后端URL: {resp.url}")
            print(f"后端返回状态码: {resp.status_code}")
            print(f"后端返回原始文本: '{resp.text}'")
            # 检查是否成功
            if resp.status_code != 200 and resp.status_code != 201:
                raise Exception(f"后端返回错误: {resp.status_code}, 内容: {resp.text}")
            
            # 只有确定有内容时才解析 JSON
            try:
                return resp.json()
            except Exception as e:
                print(f"JSON解析失败! 内容是: {resp.text}")
                raise e

    async def stop_job(self, job_id: str):
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/train/jobs/{job_id}/stop")
            return resp.json()

    async def get_job_detail(self, job_id: str):
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/train/jobs/{job_id}")
            return resp.json()

job_service = JobService()