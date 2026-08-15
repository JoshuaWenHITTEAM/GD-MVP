# Algorithm Chain Frontend API

适用后端：
- [backend_service.py](backend_service.py)

## 1. 接口概览

- `GET /healthz`
- `POST /api/stream`

后端返回方式为 `SSE` 流式数据。

## 2. 健康检查

### `GET /healthz`

用途：
- 判断服务是否正常
- 获取支持的事件类型

返回示例：

```json
{
  "status": "ok",
  "dataset_root": "./datasets/Anti-UAV-Tracking-V0",
  "supported_event_types": ["mid_gap", "sequence_transition"]
}
```

## 3. 启动任务流

### `POST /api/stream`

请求头：

```http
Content-Type: application/json
```

请求体：

```json
{
  "event_type": "mid_gap"
}
```

支持的 `event_type`：
- `mid_gap`
- `sequence_transition`

返回类型：

```http
Content-Type: text/event-stream
```

每条消息格式：

```text
data: {...json...}

```

## 4. 事件类型

后端会返回以下 `stage`：
- `start`
- `detect`
- `track`
- `done`
- `error`

## 5. 通用字段

`detect` / `track` 事件包含：

```json
{
  "task_id": "string",
  "event_type": "mid_gap",
  "stage": "detect",
  "sequence": "video10",
  "frame_index": 0,
  "frame_name": "000001.jpg",
  "reason": "init",
  "image_base64": "...",
  "image_media_type": "image/jpeg",
  "result": {}
}
```

字段说明：
- `task_id`：任务唯一标识
- `event_type`：任务类型
- `stage`：当前阶段
- `sequence`：当前序列名
- `frame_index`：当前帧索引
- `frame_name`：当前帧文件名
- `reason`：当前事件原因
- `image_base64`：当前结果图，前端直接展示
- `image_media_type`：图片类型，通常为 `image/jpeg`
- `result`：算法结果

## 6. 检测事件

`stage = "detect"`

示例：

```json
{
  "stage": "detect",
  "result": {
    "detector": "yolov8",
    "bbox_xyxy": [100, 120, 220, 260],
    "score": 0.923114,
    "num_detections": 1,
    "latency_ms": 27.431
  }
}
```

`result` 字段：
- `detector`：检测器名称
- `bbox_xyxy`：检测框 `[x1, y1, x2, y2]`
- `score`：检测分数
- `num_detections`：检测数量
- `latency_ms`：检测耗时，毫秒

## 7. 跟踪事件

`stage = "track"`

示例：

```json
{
  "stage": "track",
  "result": {
    "tracker": "avtrack",
    "bbox_xyxy": [104, 118, 224, 258],
    "score": 0.812345,
    "cache_version": 1,
    "latency_ms": 14.287
  }
}
```

`result` 字段：
- `tracker`：跟踪器名称
- `bbox_xyxy`：跟踪框 `[x1, y1, x2, y2]`
- `score`：跟踪分数
- `cache_version`：模板缓存版本
- `latency_ms`：跟踪耗时，毫秒

## 8. 开始、结束、错误事件

### `start`

```json
{
  "task_id": "xxx",
  "event_type": "mid_gap",
  "stage": "start"
}
```

### `done`

```json
{
  "task_id": "xxx",
  "event_type": "mid_gap",
  "stage": "done"
}
```

### `error`

```json
{
  "task_id": "xxx",
  "event_type": "mid_gap",
  "stage": "error",
  "error": "RuntimeError: ..."
}
```

## 9. 前端对接建议

- 调用 `POST /api/stream`
- 按流式方式读取返回
- 根据 `stage` 更新页面：
  - `detect`：更新检测图和检测结果
  - `track`：更新跟踪图和跟踪结果
  - `error`：提示错误
  - `done`：标记结束
