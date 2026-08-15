# SFK 离线中间件 Demo

这个目录是给下游应用使用的离线调试包。它包含真实硬件链路捕获的数据、模拟中间件回放程序，以及 C/Python SDK。

使用这个包不需要 RDMA 硬件。

## 目录结构

```text
sfk_demo/
  README.md
  replay_capture_to_shm.py
  captures/
    manifest.json
    rdma-prod-*.bin
  sdk/
    README.md
    c/
    python/
  examples/
    rebuild_first_image.py
    read_one_packet_from_shm.py
```

## 捕获数据

捕获数据位于：

```text
captures/
```

这是一次真实硬件运行中捕获的 5 秒数据，概要如下：

```text
总 packet 数: 5976
rdma-prod-1 timestamp: 500 个，  type=1，payload=16 bytes
rdma-prod-2 image:     500 个，  type=3，payload=1081344 bytes
rdma-prod-3 gyro:     2488 个， type=0，payload=40 bytes
rdma-prod-4 encoder:  2488 个， type=0，payload=24 bytes
```

每个 `.bin` 文件只包含中间件 packet 的 payload，不包含 13 字节中间件头。

`captures/manifest.json` 记录每个 payload 文件对应的中间件元数据，例如：

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

## 中间件 packet 格式

模拟中间件回放时，每个 payload 会被重新封装成中间件 packet：

```text
[type: 1 字节][timestamp_us: 8 字节大端][payload_len: 4 字节大端][payload]
```

本 demo 使用到的 `type`：

```text
0: 高频传感器数据，例如 gyro / encoder
1: timestamp / 低频数据
3: RDMA 原始图像分片集合
```

`type=3` 的图像 payload 是 RDMA 原始图像分片集合：

```text
4096 * 264 = 1081344 bytes
```

SDK 图像重建接口会把它转换成纯图像 bytes：

```text
4096 * 256 = 1048576 bytes
```

重建后的图像不包含中间件头。

## 环境要求

建议使用 Linux，因为模拟中间件通过 `/dev/shm` 创建共享内存。

需要：

```text
Python 3.8+
gcc 和 make，如果需要重新编译 C 动态库
```

Python SDK 会加载：

```text
sdk/c/libmidware.so
```

交付包内已经包含一个预编译的 `libmidware.so`。如果目标机器无法加载它，请重新编译：

```bash
cd sdk/c
make clean && make
cd ../..
```

## 快速测试 1：直接重建一帧图像

这个测试不使用共享内存。它直接读取一个捕获到的 `type=3` 图像 payload，并调用 Python SDK 的图像重建接口。

```bash
python3 examples/rebuild_first_image.py
```

期望输出包含：

```text
raw_payload_len=1081344 expected=1081344
rebuilt_image_len=1048576 expected=1048576
output=first_image_1024x1024.raw
```

生成的 `first_image_1024x1024.raw` 是纯 1024x1024 8-bit 灰度图像数据。

## 启动模拟中间件

执行：

```bash
python3 replay_capture_to_shm.py captures --loop
```

回放程序会读取 `captures/manifest.json`，逐个加载 payload-only `.bin` 文件，再使用记录下来的 `type` 和 `timestamp_us` 封装成中间件 packet，并写入共享内存。

默认 SHM 路径：

```text
rdma-prod-1 -> /dev/shm/shm-cons-sim-1
rdma-prod-2 -> /dev/shm/shm-cons-sim-2
rdma-prod-3 -> /dev/shm/shm-cons-sim-3
rdma-prod-4 -> /dev/shm/shm-cons-sim-4
```

测试下游程序时，请保持模拟中间件进程运行。

常用参数：

```bash
# 不按捕获时序等待，尽快回放。
python3 replay_capture_to_shm.py captures --loop --timing none

# 只回放图像流。
python3 replay_capture_to_shm.py captures --loop --source rdma-prod-2

# 覆盖默认 SHM 路径。
python3 replay_capture_to_shm.py captures \
  --image-shm /dev/shm/my-image-stream \
  --gyro-shm /dev/shm/my-gyro-stream
```

不要让真实中间件和这个模拟中间件同时写同一组 SHM 路径。

## 快速测试 2：从 SHM 读取一个 packet

先在一个终端启动模拟中间件：

```bash
python3 replay_capture_to_shm.py captures --loop
```

再在另一个终端执行：

```bash
python3 examples/read_one_packet_from_shm.py --source rdma-prod-2
```

期望输出包含：

```text
source=rdma-prod-2
type=3
payload_len=1081344
rebuilt_image_len=1048576
```

这说明下游程序可以通过 SDK 从 SHM 读到中间件 packet，并且图像 SDK 能正确重建图像。

## 下游集成方式

推荐第二种方式。

### 方式 1：直接测试 payload

直接读取 `captures/manifest.json` 和 `.bin` 文件，然后调用 SDK 接口。

例如测试图像重建：

```python
from midware import rebuild_rdma_image

payload = open("captures/rdma-prod-2-000001.bin", "rb").read()
image = rebuild_rdma_image(payload)
```

这种方式适合只验证图像重建 SDK 接口。

### 方式 2：通过 SHM 模拟中间件

启动：

```bash
python3 replay_capture_to_shm.py captures --loop
```

然后下游应用从 `/dev/shm` 中读取中间件 packet。

真实链路是：

```text
中间件 -> SHM -> 下游应用
```

离线模拟链路是：

```text
离线 payload 文件 -> replay_capture_to_shm.py -> SHM -> 下游应用
```

## C SDK

编译：

```bash
cd sdk/c
make clean && make
```

C SDK 提供：

```text
packet 序列化 / 解析
SHM producer / consumer
RDMA 图像重建
```

主要头文件：

```text
sdk/c/midware_packet.h
sdk/c/midware_shm.h
sdk/c/midware_image.h
```

## Python SDK

如果需要在自己的 Python 程序中直接使用 SDK，建议不要覆盖已有的 `PYTHONPATH`。

临时运行某个脚本时，推荐使用一次性环境变量：

```bash
PYTHONPATH="$PWD/sdk/python:${PYTHONPATH:-}" python3 your_app.py
```

如果要在当前 shell 中设置，也应保留原值：

```bash
export PYTHONPATH="$PWD/sdk/python:${PYTHONPATH:-}"
```

也可以在自己的 Python 程序中显式添加包内 SDK 路径：

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT / "sdk" / "python"))
```

然后：

```python
from midware import ShmConsumer, ShmProducer, rebuild_rdma_image
```

`replay_capture_to_shm.py` 和 `examples/` 目录下的示例脚本已经自动添加了包内 SDK 路径，不需要手动设置 `PYTHONPATH`。
