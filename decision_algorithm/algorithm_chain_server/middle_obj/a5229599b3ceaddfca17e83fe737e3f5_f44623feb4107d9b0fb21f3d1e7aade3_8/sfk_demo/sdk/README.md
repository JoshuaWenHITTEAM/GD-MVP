# SDK 说明

这个交付包只包含 **C SDK** 和 **Python SDK**。

不包含 Java SDK。

## 中间件数据包格式

中间件数据包由 13 字节头部和 payload 组成：

```text
[type: 1 字节][timestamp_us: 8 字节大端][payload_len: 4 字节大端][payload]
```

当前使用到的 `type`：

```text
0: 高频传感器数据，例如 gyro / encoder
1: 低频或 timestamp 数据
2: 已重建的完整图像帧
3: RDMA 原始图像分片集合
```

`../captures/` 目录下的 `.bin` 文件只包含 payload，不包含上面的 13 字节中间件头。

如果需要恢复完整的中间件数据包，需要读取 `../captures/manifest.json` 中记录的 `type`、`timestamp_us`、`source` 和文件顺序。

## C SDK

文件：

```text
sdk/c/midware_packet.h
sdk/c/midware_packet.c
sdk/c/midware_shm.h
sdk/c/midware_shm.c
sdk/c/midware_image.h
sdk/c/midware_image.c
sdk/c/Makefile
```

编译：

```bash
cd sdk/c
make clean && make
```

主要接口：

```c
midware_shm_ctx_t* midware_shm_producer_init(const char* path, uint64_t capacity);

midware_shm_ctx_t* midware_shm_consumer_init(const char* path);

bool midware_shm_write_packet(
    midware_shm_ctx_t* ctx,
    uint8_t type,
    uint64_t timestamp_us,
    const void* payload,
    uint32_t payload_len
);

int32_t midware_shm_read_packet(
    midware_shm_ctx_t* ctx,
    void* buf,
    int32_t max_len,
    midware_packet_header_t* out_header,
    const void** out_payload
);

int32_t midware_rebuild_rdma_image(
    const void* raw_slices,
    uint32_t raw_len,
    void* out_image,
    uint32_t out_capacity
);
```

### RDMA 图像 payload

`type=3` 的图像 payload 是 RDMA 原始图像分片集合：

```text
4096 * 264 = 1081344 bytes
```

每个 264 字节分片的布局是：

```text
[8 字节分片头][256 字节图像数据]
```

SDK 重建后的图像是纯图像 bytes：

```text
4096 * 256 = 1048576 bytes
```

注意：图像重建接口返回的是纯图像数据，不包含 `type=2` 的中间件头。

## Python SDK

文件：

```text
sdk/python/midware.py
sdk/c/libmidware.so
```

Python SDK 通过 `ctypes` 加载：

```text
sdk/c/libmidware.so
```

如果目标机器上无法加载随包提供的 `libmidware.so`，需要重新编译 C SDK：

```bash
cd sdk/c
make clean && make
```

使用 Python SDK 时，建议不要覆盖已有的 `PYTHONPATH`。

临时运行某个脚本时，推荐使用一次性环境变量：

```bash
PYTHONPATH="$PWD/sdk/python:${PYTHONPATH:-}" python3 your_app.py
```

如果确实要在当前 shell 中设置，也应保留原值：

```bash
export PYTHONPATH="$PWD/sdk/python:${PYTHONPATH:-}"
```

也可以在自己的 Python 程序中显式添加 SDK 路径：

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "sdk" / "python"))
```

### 从 SHM 读取中间件 packet

```python
from midware import ShmConsumer

consumer = ShmConsumer("/dev/shm/shm-cons-sim-2")
pkt = consumer.read_packet()

if pkt is not None:
    print(pkt.type, pkt.timestamp_us, len(pkt.payload))

consumer.close()
```

### 向 SHM 写入中间件 packet

```python
from midware import ShmProducer

producer = ShmProducer("/dev/shm/shm-cons-sim-2", 1081344 + 13)
producer.write_packet(payload, type_id=3, timestamp_us=123456)
producer.close()
```

### 重建捕获到的 RDMA 图像 payload

```python
from midware import rebuild_rdma_image

raw_payload = open("../captures/rdma-prod-2-000001.bin", "rb").read()
image = rebuild_rdma_image(raw_payload)
```

这里的 `image` 是纯图像 bytes，不包含中间件头。

## 捕获数据和 manifest

捕获数据位于：

```text
captures/
```

其中：

```text
captures/manifest.json
captures/rdma-prod-1-*.bin
captures/rdma-prod-2-*.bin
captures/rdma-prod-3-*.bin
captures/rdma-prod-4-*.bin
```

`.bin` 文件是 payload-only。

`manifest.json` 用来描述每个 payload 文件对应的中间件元数据，例如：

```json
{
  "source": "rdma-prod-2",
  "index": 1,
  "file": "rdma-prod-2-000001.bin",
  "type": 3,
  "timestamp_us": 1777358655458995,
  "payload_len": 1081344
}
```

如果要模拟中间件行为，请使用交付包根目录下的：

```text
replay_capture_to_shm.py
```
