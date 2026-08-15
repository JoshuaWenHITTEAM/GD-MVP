# 训练控制台后端

## 启动

建议在 `CVRL` 环境中启动：

```bash
cd decision_algorithm/RL_train
conda run -n CVRL uvicorn training_console_backend.main:app --host 0.0.0.0 --port 30000
```

## 接口

- `POST /api/train/jobs`
- `GET /api/train/jobs`
- `GET /api/train/jobs/{job_id}`
- `POST /api/train/jobs/{job_id}/stop`
- `GET /api/train/jobs/{job_id}/stream`

## 启动训练请求示例

```json
{
  "task_type": "detect",
  "train_config": {
    "total_timesteps": 400,
    "learning_rate": 0.0001,
    "batch_size": 32,
    "buffer_size": 2000
  }
}
```

## SSE 事件

- `status`
- `progress`
- `log`
- `metrics`
- `checkpoint`
- `completed`
- `failed`
