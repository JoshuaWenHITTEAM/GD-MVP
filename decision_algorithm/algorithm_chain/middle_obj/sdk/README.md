# 中间件共享内存 (SHM) SDK

本 SDK 提供基于共享内存 (SHM) 的高性能进程间通信能力，采用 **基于 slot（槽位）的零拷贝** 设计。它与 Java 中间件的 V2 共享内存布局和 Packet 二进制协议保持兼容，可用于 C、Python 与 Java 进程之间传递数据。

## 零拷贝架构

- **预分配 slot**：生产者初始化时通过 `capacity` 指定单个 slot 的大小，即单条消息的最大字节数。
- **索引队列传输**：队列项只保存 `slotIndex` 和 `length`，每项 8 字节。
- **数据区写入**：消息内容直接写入对应 slot，队列只引用该 slot，避免在共享内存内部维护额外数据副本。
- **覆盖策略**：队列满时会推进读指针并覆盖最旧数据，适合只关心近期数据的高频流。

### 内存布局

共享内存元数据统一使用 **64-bit 大端序 (Big-Endian, BE)**。当前 C/Java V2 实现使用 256 个队列项，数据区从偏移量 `2304` 开始。

```text
[0..63]      Producer cache line
    [0..7]       WRITE_POS (8B BE)
    [8..15]      CACHED_READ_POS (8B BE)
    [16..23]     OVERWRITE_COUNT (8B BE)
    [24..31]     NEXT_SLOT (8B BE)

[64..127]    Consumer cache line
    [64..71]     READ_POS (8B BE)
    [72..79]     CACHED_WRITE_POS (8B BE)
    [80..87]     CONSUME_COUNT (8B BE)

[128..191]   Config cache line
    [128..135]   MAGIC "SHMMIDW2" (8B BE)
    [136..143]   VERSION = 2 (8B BE)
    [144..151]   FORMAT_READY = (format << 32 | ready) (8B BE)
    [152..159]   SLOT_COUNT (8B BE)
    [160..167]   SLOT_SIZE  (8B BE)

[192..255]   Reserved cache line
[256..2303]  INDEX_QUEUE (256 entries x 8B BE)
[2304..]     SLOTS data area
```

## 数据包协议

Packet API 会在原始 payload 前添加 13 字节头部。头部字段使用大端序编码，格式如下：

| 偏移量 | 字段 | 大小 | 说明 |
| --- | --- | --- | --- |
| 0 | `Type` | 1 byte | 数据类型 ID，范围 `0..255`；当前约定见下表 |
| 1 | `Timestamp` | 8 bytes | 微秒级时间戳 |
| 9 | `Length` | 4 bytes | payload 长度 |
| 13 | `Payload` | N bytes | 实际业务数据 |

当前内置类型：

| Type | 名称 | Payload |
| --- | --- | --- |
| `0` | 高频数据 | 高频传感器业务数据 |
| `1` | 低频数据 | 低频/事件类业务数据 |
| `2` | 完整图像帧 | 重建后的纯图像数据，当前为 `4096 * 256 = 1048576` 字节 |
| `3` | RDMA 原始图像分片集合 | `4096` 个原始 RDMA 图像分片连续拼接，每片 `264` 字节，总长度 `1081344` 字节 |
| `255` | 控制指令 | 当前用于转台位置指向控制，payload 固定 9 字节 |

`type=255` 的控制指令 payload 布局如下。中间件 packet 头部使用大端序；该 payload 内部的角度字段也使用 32-bit 大端序整数，单位为度。

| Payload 偏移量 | 字段 | 大小 | 编码 | 说明 |
| --- | --- | --- | --- | --- |
| `0` | `adapter` | 1 byte | `uint8` | 控制适配器 ID；`0x00` 表示当前适配的 RS422 转台 |
| `1..4` | `azimuth` | 4 bytes | `int32_be` | 方位角，整数度，合法范围 `0..359` |
| `5..8` | `pitch` | 4 bytes | `int32_be` | 俯仰角，整数度，合法范围 `0..359` |

角度编码规则：

- 中间件 payload 中的 `azimuth` 和 `pitch` 直接保存整数角度，不保存 `angle * 10000` 后的转台内部值。
- 合法范围为闭区间 `0..359`；生产端和控制端都应拒绝范围外的值。
- `adapter=0x00` 时，控制端把整数角度转换为当前转台位置指向模式需要的 `angle * 10000`，再写入转台串口帧的 `D4-D9`：`AA CC 01 07 <azimuth_scaled_le24> <pitch_scaled_le24> 00 <checksum> 55`。

示例：控制当前转台指向方位角 `10` 度、俯仰角 `5` 度：

```text
payload = 00 00 00 00 0A 00 00 00 05

00          adapter = 当前 RS422 转台
00 00 00 0A azimuth = 10
00 00 00 05 pitch   = 5
```

`type=3` 的单个 RDMA 图像分片布局为：

```text
[0..7]   8-byte slice header
[8..263] 256-byte image payload
```

SDK 的图像重建接口输入 `type=3` 的 payload，输出纯图像 bytes，不包含 `type=2` 的 13 字节中间件包头。

## C 语言 SDK

- **位置**：`sdk/c`
- **库文件**：`libmidware.so`
- **头文件**：`midware_shm.h`

### 编译

```bash
cd sdk/c
make clean && make
```

Python SDK 通过 `ctypes` 加载 `sdk/c/libmidware.so`，因此使用 Python 前也需要先完成上述编译。

### 初始化

```c
#include "midware_shm.h"
#include "midware_image.h"
#include <string.h>

// 创建生产者。capacity 表示单个 slot 的大小，也就是单条消息的最大长度。
midware_shm_ctx_t* p_ctx = midware_shm_producer_init(
    "/dev/shm/demo_stream",
    1024 * 1024
);

// 连接到已有的共享内存文件。
midware_shm_ctx_t* c_ctx = midware_shm_consumer_init("/dev/shm/demo_stream");
```

### Packet API（推荐）

Packet API 适合需要统一数据类型、时间戳和 payload 长度的消息流。写入时会自动序列化 packet，读取时会自动解析头部。

**写入 packet**

```c
uint8_t type = 2;       // 例如：视频帧
uint64_t ts = 100000;   // 微秒级时间戳
const char* data = "frame_data";

bool ok = midware_shm_write_packet(p_ctx, type, ts, data, strlen(data));
```

**重建 RDMA 原始图像分片**

```c
uint8_t image[MIDWARE_RDMA_IMAGE_REBUILT_SIZE];
int32_t written = midware_rebuild_rdma_image(
    raw_slices,
    MIDWARE_RDMA_IMAGE_RAW_SIZE,
    image,
    sizeof(image)
);

if (written == MIDWARE_RDMA_IMAGE_REBUILT_SIZE) {
    // image 是纯图像数据，不包含中间件 packet 头。
}
```

如果已读取到完整 `type=3` packet，也可以直接从 packet 重建：

```c
int32_t written = midware_rebuild_rdma_image_from_packet(
    packet,
    packet_len,
    image,
    sizeof(image)
);
```

**读取下一条 packet**

```c
char buf[1024];
midware_packet_header_t header;
const void* payload_ptr;

int len = midware_shm_read_packet(c_ctx, buf, sizeof(buf), &header, &payload_ptr);

if (len > 0) {
    // header.type, header.timestamp_us, header.payload_len 已解析完成。
    // payload_ptr 指向 buf 内部的 payload 起始位置。
}
```

返回值约定：

| 返回值 | 含义 |
| --- | --- |
| `> 0` | 读取并解析成功，返回本条 packet 的总字节数 |
| `0` | 暂无可读数据 |
| `> max_len` | 缓冲区太小，返回值是所需缓冲区大小 |
| `-1` | SHM 内部错误 |
| `-2` | 数据不符合 Packet 协议，解析失败 |

**读取最新 packet**

```c
char buf[1024];
midware_packet_header_t header;
const void* payload_ptr;

int len = midware_shm_read_latest_packet(
    c_ctx,
    buf,
    sizeof(buf),
    &header,
    &payload_ptr
);

if (len > 0) {
    // 只返回最新 packet；更旧的未读数据会被丢弃。
}
```

### 原始字节 API

原始字节 API 不添加 Packet 头部，适合调用方已经有自定义协议或只需要传递不透明字节流的场景。

**写入原始字节**

```c
bool ok = midware_shm_write(p_ctx, raw_data, len);
```

**读取下一条原始字节消息**

```c
int len = midware_shm_read(c_ctx, buf, sizeof(buf));
```

**读取最新原始字节消息**

```c
int len = midware_shm_read_latest(c_ctx, buf, sizeof(buf));
```

原始字节读取同样返回 `> 0` 表示成功、`0` 表示暂无数据、`> max_len` 表示缓冲区太小、`-1` 表示错误。

### 资源清理

```c
midware_shm_close(ctx);
```

`midware_shm_close` 会解除映射并关闭文件描述符，但不会删除共享内存文件。

## Python SDK

- **位置**：`sdk/python`
- **模块**：`midware.py`

### 使用示例

```python
from midware import ShmProducer, ShmConsumer

path = "/dev/shm/demo_stream"

producer = ShmProducer(path, capacity=1024 * 1024)
consumer = ShmConsumer(path)

# 写入 packet。SDK 会自动序列化头部。
producer.write_packet(
    b"payload_data",
    type_id=1,
    timestamp_us=123456,
)

pkt = consumer.read_packet()
if pkt is not None:
    print(f"type={pkt.type} timestamp={pkt.timestamp_us} len={len(pkt.payload)}")

# 写入和读取原始字节。
producer.write(b"raw_bytes")
data = consumer.read()

# 只读取最新数据，并丢弃更旧的未读数据。
latest_pkt = consumer.read_latest_packet()
latest_data = consumer.read_latest()

producer.close()
consumer.close()
```

Python 接口返回值约定：

| 方法 | 有数据时返回 | 无数据时返回 |
| --- | --- | --- |
| `read_packet()` | `PacketObj(type, timestamp_us, payload)` | `None` |
| `read_latest_packet()` | `PacketObj(type, timestamp_us, payload)` | `None` |
| `read()` | `bytes` | `None` |
| `read_latest()` | `bytes` | `None` |

### 独立协议工具

如果只需要 Packet 协议的序列化和反序列化，不需要经过 SHM 传输，可以直接使用以下工具函数。例如，将 packet 编码后通过 UDP、文件或其他通道传输。

```python
from midware import serialize_packet, parse_packet

raw = serialize_packet(
    type_id=1,
    timestamp_us=123456,
    payload=b"hello",
)

pkt = parse_packet(raw)
if pkt is not None:
    print(pkt.type, pkt.timestamp_us, pkt.payload)
```

### RDMA 图像重建工具

```python
from midware import (
    TYPE_RDMA_IMAGE_RAW,
    rebuild_rdma_image,
    rebuild_rdma_image_from_packet,
)

# raw_slices 是 type=3 packet 的 payload，长度为 4096 * 264。
image = rebuild_rdma_image(raw_slices)

# image 是纯图像 bytes，长度为 4096 * 256，不包含中间件 packet 头。

pkt = parse_packet(raw_packet)
if pkt is not None and pkt.type == TYPE_RDMA_IMAGE_RAW:
    image = rebuild_rdma_image(pkt.payload)

# 或直接从完整 type=3 packet 重建。
image = rebuild_rdma_image_from_packet(raw_packet)
```

## Java SDK

Java 侧图像重建工具位于 `org.example.sdk.RdmaImageRebuilder`：

```java
import org.example.sdk.RdmaImageRebuilder;

byte[] image = RdmaImageRebuilder.rebuild(rawSlices);

// rawPacket 是完整 type=3 中间件包；返回值仍然是纯图像 bytes。
byte[] imageFromPacket = RdmaImageRebuilder.rebuildFromPacket(rawPacket);
```

返回的 `image` 长度为 `RdmaImageRebuilder.REBUILT_SIZE`，不包含中间件 packet 头。
