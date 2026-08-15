# 中间件共享内存 (SHM) SDK

本 SDK 提供基于共享内存 (SHM) 的高性能进程间通信能力，采用 **基于 slot（槽位）的零拷贝** 设计。它与 Java 中间件的 V2 共享内存布局和 Packet 二进制协议保持兼容，可用于 C、Python 与 Java 进程之间传递数据。

## 零拷贝架构

- **预分配 slot**：中间件初始化 SHM 时指定单个 slot 的大小，即单条消息的最大字节数。
- **默认 slot 数**：Java 配置 `type: shm` 未指定 `slotCount` 时使用 `32`；业务侧 SDK 只 attach 已有 SHM 并校验 header。
- **索引队列传输**：队列项只保存 `slotIndex` 和 `length`，每项 8 字节。
- **数据区写入**：消息内容直接写入对应 slot，队列只引用该 slot，避免在共享内存内部维护额外数据副本。
- **覆盖策略**：队列满时会推进读指针并覆盖最旧数据，适合只关心近期数据的高频流。

### 内存布局

共享内存元数据统一使用 **64-bit 大端序 (Big-Endian, BE)**。当前 C/Java V2 实现使用 256 个固定队列项，数据区从偏移量 `2304` (`SLOTS_OFFSET`) 开始。实际文件大小为 `2304 + slotCount * slotSize`。

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
| `254` | 设备反馈 | 相机/转台等设备反馈 |
| `255` | 控制指令 | 统一控制指令，payload 格式见 `docs/packet_format.md` |

`type=255` 的控制指令 payload 由 `deviceType(uint16_be) + commandType(uint16_be) + parameters(...)` 组成。设备类型、指令类型和参数顺序以 `app/src/main/resources/instructions/` 下的 YAML 指令规范为准；详细协议说明见 `docs/packet_format.md`。

`type=254` 的设备反馈 payload 由 `version + deviceType + subjectType + feedbackKind + status + requestTimestampUs + dataFormat + data` 组成，固定头部为 18 字节。`requestTimestampUs` 用于匹配原控制指令 Packet 头中的时间戳。详细协议说明见 `docs/packet_format.md`。

### TCP/UDP 传输约定

SDK 的 TCP/UDP 接口直接传输上述完整 Packet：

- UDP：一个 datagram 承载一个完整 Packet。
- TCP：连续写入完整 Packet，接收端按 Packet 头部的 `Length` 字段拆帧，不额外添加 TCP 长度前缀。

外部程序作为 producer 时，UDP 发送到中间件 UDP receiver，TCP 作为 client 连接中间件 TCP receiver。外部程序作为 consumer 时可以使用两种 TCP 方式：旧方式是外部程序 listen、中间件 TCP sender 作为 client 连接；控制/反馈闭环推荐方式是中间件 TCP sender 配置 `mode: server`，外部程序作为 client 连接中间件后读取 Packet。

`type=3` 的单个 RDMA 图像分片布局为：

```text
[0..7]   8-byte slice header
[8..263] 256-byte image payload
```

SDK 的图像重建接口输入 `type=3` 的 payload，输出纯图像 bytes，不包含 `type=2` 的 13 字节中间件包头。

## C 语言 SDK

- **位置**：`sdk/c`
- **库文件**：`libmidware.so`
- **头文件**：`midware_shm.h`、`midware_net.h`、`midware_image.h`

### 编译

```bash
cd sdk/c
make clean && make
```

Python SDK 通过 `ctypes` 加载 `sdk/c/libmidware.so`，因此使用 Python 前也需要先完成上述编译。

### 连接已有 SHM

SHM 文件必须先由中间件按配置创建和初始化。业务侧 writer 只 attach
已有 SHM，不创建、不扩容、不重置 header 或读写位置。

```c
#include "midware_shm.h"
#include "midware_image.h"
#include <string.h>

// 连接到已有 writer 端点。capacity 表示调用方需要的最小单 slot 大小。
midware_shm_ctx_t* p_ctx = midware_shm_writer_attach(
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

### TCP/UDP API

C 网络接口位于 `midware_net.h`，使用阻塞式超时模型。`timeout_ms < 0` 表示一直等待，`timeout_ms == 0` 表示立即返回，`timeout_ms > 0` 表示最多等待指定毫秒数。

统一返回约定：

| 返回值 | 含义 |
| --- | --- |
| `> 0` | 成功，返回读写字节数 |
| `0` | 超时或暂无数据 |
| `> max_len` | 读取缓冲区太小，返回所需长度且数据未被消费 |
| `-1` | socket 系统错误 |
| `-2` | Packet 格式错误 |
| `-3` | TCP 连接关闭 |

**UDP 发送/接收 Packet**

```c
#include "midware_net.h"

midware_udp_socket_t* out = midware_udp_open("0.0.0.0", 0, 1000);
midware_udp_send_packet(out, "127.0.0.1", 51001, MIDWARE_TYPE_LOW_FREQ, 123456,
                        "hello", 5);
midware_udp_close(out);

midware_udp_socket_t* in = midware_udp_open("0.0.0.0", 60001, 1000);
uint8_t buf[4096];
midware_packet_header_t header;
const void* payload;
int32_t len = midware_udp_recv_packet(in, buf, sizeof(buf), &header, &payload,
                                      NULL, 0, NULL);
midware_udp_close(in);
```

**TCP 发送/接收 Packet**

```c
midware_tcp_conn_t* producer = midware_tcp_connect("127.0.0.1", 51101, 1000);
midware_tcp_send_packet(producer, MIDWARE_TYPE_LOW_FREQ, 123456, "hello", 5);
midware_tcp_conn_close(producer);

midware_tcp_server_t* server = midware_tcp_listen("0.0.0.0", 60101, 16, 1000);
midware_tcp_conn_t* consumer = midware_tcp_accept(server);
uint8_t buf[4096];
midware_packet_header_t header;
const void* payload;
int32_t len = midware_tcp_read_packet(consumer, buf, sizeof(buf),
                                      MIDWARE_NET_DEFAULT_MAX_FRAME_LENGTH,
                                      &header, &payload);
midware_tcp_conn_close(consumer);
midware_tcp_server_close(server);
```

### 控制/反馈 SDK

C 控制/反馈接口位于 `midware_control.h`，相机硬件帧示例 codec 位于 `midware_camera.h`。C SDK 不打开串口，也不负责线程调度和重试策略；板卡程序负责连接中间件、调用 codec、写硬件、再发送反馈。

**读取控制指令**

```c
#include "midware_control.h"

midware_tcp_conn_t* conn = midware_tcp_connect("127.0.0.1", 55201, 1000);
uint8_t packet_buf[4096];
midware_control_command_t cmd;

int32_t len = midware_control_read(conn, packet_buf, sizeof(packet_buf),
                                   MIDWARE_NET_DEFAULT_MAX_FRAME_LENGTH, &cmd);
if (len > 0) {
    // cmd.device_type, cmd.command_type, cmd.params/cmd.params_len
    // cmd.request_timestamp_us 来自 type=255 Packet 头，用于反馈匹配。
}
```

**相机逻辑命令转硬件帧**

```c
#include "midware_camera.h"

uint8_t frame[64];
uint32_t frame_len = 0;
int rc = midware_camera_command_to_frame(&cmd, frame, sizeof(frame), &frame_len);
if (rc == 0) {
    // 板卡程序把 frame[0..frame_len) 写给相机。
}
```

相机 codec 覆盖 `camera_commands.yaml` 中的 28 条相机逻辑命令：激光 11 条、镜头 17 条。命令常量由 `scripts/generate_control_specs.py` 生成，其中 `lens_stop=0x0211`，APD 电源拆分为 `laser_apd_power_on/off`。

**发送设备反馈**

```c
midware_feedback_send(conn,
                      MIDWARE_DEVICE_CAMERA,
                      cmd.command_type,
                      MIDWARE_FEEDBACK_ACK,
                      MIDWARE_STATUS_OK,
                      cmd.request_timestamp_us,
                      MIDWARE_DATA_NONE,
                      NULL,
                      0);
```

**端到端 smoke**

仓库提供了一个闭环 smoke，可临时生成四端口中间件配置、启动 `MainMidware`、启动 C 板卡 mock，并由 Python `CameraClient` 发送全部 28 条相机逻辑命令：

```bash
scripts/control_feedback_e2e.py
```

脚本会验证：

- Python 发送 `type=255` 控制指令到 `algo-command-in`。
- C 板卡 mock 从 `board-command-out` 读取控制指令，调用相机 codec 生成硬件帧。
- C 板卡 mock 向 `board-feedback-in` 发送 `type=254 ack`。
- Python 从 `algo-feedback-out` 读取反馈，并按 `requestTimestampUs` 匹配成功。
- 无板卡订阅时请求按 timeout 失败，中间件不持久缓存控制指令。

## Python SDK

- **位置**：`sdk/python`
- **模块**：`midware.py`

### 使用示例

```python
from midware import ShmProducer, ShmConsumer

path = "/dev/shm/demo_stream"

# path 必须已经由中间件创建并初始化；ShmProducer 只 attach。
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

Python `ShmProducer(path, capacity)` 中的 `capacity` 是单个 slot 的最大 packet 大小，不是整个 SHM 文件大小。对应中间件 YAML 的 `shmSize` 是总容量预算；未显式配置 `slotSize` 时，中间件按 `(shmSize - 2304) / slotCount` 计算单槽大小。如果 `path` 不存在、header 不是中间件初始化的格式，或已有 `slotSize` 小于 `capacity`，`ShmProducer` 会 attach 失败并抛出异常。

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

### TCP/UDP API

Python 网络接口使用标准库 `socket`，超时时返回 `None`。

**UDP 发送/接收**

```python
from midware import UdpProducer, UdpConsumer

consumer = UdpConsumer(bind_host="0.0.0.0", port=60001, timeout_ms=1000)
producer = UdpProducer("127.0.0.1", 51001, timeout_ms=1000)

producer.write_packet(b"hello", type_id=1, timestamp_us=123456)
pkt = consumer.read_packet()

producer.close()
consumer.close()
```

**TCP 发送/接收**

```python
from midware import TcpProducer, TcpConsumer

producer = TcpProducer("127.0.0.1", 51101, timeout_ms=1000)
producer.write_packet(b"hello", type_id=1, timestamp_us=123456)
producer.close()

consumer = TcpConsumer(bind_host="0.0.0.0", port=60101, timeout_ms=1000)
pkt = consumer.read_packet()
consumer.close()
```

`TcpProducer.write_packet_bytes(raw_packet)` 可发送已经由 `serialize_packet()` 编码好的完整 Packet；`TcpConsumer.read_packet_bytes()` 返回完整 Packet bytes。

### 控制/反馈 SDK

Python 算法侧只使用逻辑接口和反馈对象，不接触相机/转台原始硬件帧。

```python
from midware import (
    CameraClient,
    STATUS_OK,
    build_control_payload,
    build_feedback_payload,
    parse_feedback_payload,
    DEVICE_CAMERA,
    COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE,
)

payload = build_control_payload(
    DEVICE_CAMERA,
    COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE,
    periodMs=1000,
)
# payload == b"\x00\x02\x01\x03\x03\xE8"

camera = CameraClient(
    command_host="127.0.0.1",
    command_port=55101,
    feedback_host="127.0.0.1",
    feedback_port=55202,
    timeout_ms=1000,
)
feedback = camera.laser_continuous_measure(1000)
if feedback.status == STATUS_OK:
    print("accepted")
camera.close()
```

正式相机链路使用 SHM 接入中间件。控制方法返回底层 `DeviceFeedback`，需要相机业务字段时调用 `parse_camera_feedback()`：

```python
from midware import CameraShmClient, STATUS_OK, parse_camera_feedback

camera = CameraShmClient(
    command_shm_path="/dev/shm/shm-prod-camera-command",
    feedback_shm_path="/dev/shm/shm-cons-camera-feedback",
    command_capacity=65536,
    timeout_ms=1000,
)
feedback = camera.lens_query_zoom()
if feedback.status == STATUS_OK:
    parsed = parse_camera_feedback(feedback)
    print(parsed["data"]["lensPositionType"], parsed["data"]["position"])
camera.close()
```

`CameraShmClient(command_shm_path, feedback_shm_path, command_capacity=...)` 保持原签名；`command_capacity` 表示命令 SHM 的单个 zero-copy slot 最大 packet 大小。相机命令 `/dev/shm/shm-prod-camera-command` 和反馈 `/dev/shm/shm-cons-camera-feedback` 均使用 `SHMMIDW2` zero-copy slot SHM。

持续反馈或不需要先发命令的读取可以使用：

```python
parsed = camera.read_parsed_feedback(timeout_ms=1000)
if parsed is not None:
    print(parsed["subjectKey"], parsed["dataFormatName"], parsed["data"])
```

`CameraShmClient` 和旧 TCP `CameraClient` 都提供 `camera_commands.yaml` 中全部 28 条相机逻辑命令的 snake_case 方法，例如 `laser_continuous_measure(period_ms)`、`laser_set_nearest_distance(distance_m)`、`lens_relay_on(relay_id)`、`lens_goto_zoom(position)`、`lens_stop()`。旧反馈会优先使用控制指令 Packet 头的 `timestampUs` 与反馈中的 `requestTimestampUs` 匹配；真实裸板接口封出的 `requestTimestampUs=0` 反馈会按 `subjectType` 兜底匹配。`CameraClient` 保留用于旧 TCP 算法接入和测试。

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
