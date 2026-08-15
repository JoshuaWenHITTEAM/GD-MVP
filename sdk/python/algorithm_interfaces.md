| 能力 | 接口/对象 | 方法 | 参数 | 返回 | 功能 |
|---|---|---|---|---|---|
| 读图 | `ShmConsumer` | `ShmConsumer(path)` | `path: str`，图像共享内存路径，当前常用 `/dev/shm/shm-cons-sim-2` | `ShmConsumer` | 创建图像共享内存消费者，用于从 midware 输出的图像 SHM 读取数据。 |
| 读图 | `ShmConsumer` | `read_latest_packet()` | 无 | `PacketObj` 或 `None` | 读取最新图像包并丢弃旧包；`pkt.type == TYPE_IMAGE_FRAME` 时 `pkt.payload` 是图像数据，`pkt.type == TYPE_RDMA_IMAGE_RAW` 时需要先重建。 |
| 读图 | `ShmConsumer` | `read_packet()` | 无 | `PacketObj` 或 `None` | 按顺序读取下一包数据；适合需要逐包处理图像流的算法。 |
| 读图 | `midware` 函数 | `rebuild_rdma_image(raw_slices)` | `raw_slices: bytes`，`TYPE_RDMA_IMAGE_RAW` 包的 payload | `bytes` | 将 RDMA 原始切片数据重建为连续图像字节，当前对应 1024 x 1024 的 uint8 图像。 |
| 读图 | `midware` 函数 | `rebuild_rdma_image_from_packet(data)` | `data: bytes`，完整 midware packet 字节 | `bytes` | 从完整 packet 中解析 RDMA 原始图像并重建为连续图像字节。 |
| 读相机反馈 | `CameraShmClient` | `CameraShmClient(command_shm_path, feedback_shm_path, command_capacity=65536, timeout_ms=1000)` | `command_shm_path: str`，当前常用 `/dev/shm/shm-prod-camera-command`；`feedback_shm_path: str`，当前常用 `/dev/shm/shm-cons-camera-feedback`；`command_capacity: int`；`timeout_ms: int` | `CameraShmClient` | 创建相机共享内存客户端；同一个对象既能发送相机控制指令，也能读取相机反馈。 |
| 读相机反馈 | `CameraShmClient` | `read_feedback(timeout_ms=None)` | `timeout_ms: int` 或 `None` | `DeviceFeedback` 或 `None` | 读取一条相机反馈并返回原始结构化反馈对象；超时未读到时返回 `None`。 |
| 读相机反馈 | `CameraShmClient` | `read_parsed_feedback(timeout_ms=None)` | `timeout_ms: int` 或 `None` | `dict` 或 `None` | 读取一条相机反馈并解析成字典，适合算法直接使用；包含设备、指令、状态、数据格式和业务数据。 |
| 读相机反馈 | `CameraShmClient` | `parse_feedback(feedback)` | `feedback: DeviceFeedback` | `dict` | 将已读取到的 `DeviceFeedback` 转成可读字典。 |
| 读相机反馈 | `midware` 函数 | `parse_feedback_payload(payload)` | `payload: bytes`，`TYPE_DEVICE_FEEDBACK` 包的 payload | `DeviceFeedback` | 将设备反馈 payload 解析为统一反馈结构。 |
| 读相机反馈 | `midware` 函数 | `parse_camera_feedback(feedback)` | `feedback: DeviceFeedback` | `dict` | 将相机反馈结构解析为算法侧更容易读取的字典。 |
| 发相机控制 | `CameraShmClient` | `laser_standby(timeout_ms=None)` | `timeout_ms: int` 或 `None` | `DeviceFeedback` | 激光待机。 |
| 发相机控制 | `CameraShmClient` | `laser_single_measure(timeout_ms=None)` | `timeout_ms: int` 或 `None` | `DeviceFeedback` | 激光单次测距。 |
| 发相机控制 | `CameraShmClient` | `laser_continuous_measure(period_ms, timeout_ms=None)` | `period_ms: int`，范围 0-65535；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 激光连续测距，`period_ms` 表示测距周期，单位 ms。 |
| 发相机控制 | `CameraShmClient` | `laser_self_test(timeout_ms=None)` | `timeout_ms: int` 或 `None` | `DeviceFeedback` | 激光自检。 |
| 发相机控制 | `CameraShmClient` | `laser_set_nearest_distance(distance_m, timeout_ms=None)` | `distance_m: int`，范围 0-65535；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 设置激光最近距离，单位 m。 |
| 发相机控制 | `CameraShmClient` | `laser_query_shot_count(timeout_ms=None)` | `timeout_ms: int` 或 `None` | `DeviceFeedback` | 查询激光累计出光次数。 |
| 发相机控制 | `CameraShmClient` | `laser_set_farthest_distance(distance_m, timeout_ms=None)` | `distance_m: int`，范围 0-65535；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 设置激光最远距离，单位 m。 |
| 发相机控制 | `CameraShmClient` | `laser_apd_power_on(timeout_ms=None)` | `timeout_ms: int` 或 `None` | `DeviceFeedback` | 打开激光 APD 电源。 |
| 发相机控制 | `CameraShmClient` | `laser_apd_power_off(timeout_ms=None)` | `timeout_ms: int` 或 `None` | `DeviceFeedback` | 关闭激光 APD 电源。 |
| 发相机控制 | `CameraShmClient` | `laser_set_work_timeout(timeout_min, timeout_ms=None)` | `timeout_min: int`，范围 0-65535；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 设置激光连续工作超时时间，单位 min。 |
| 发相机控制 | `CameraShmClient` | `laser_query_id(timeout_ms=None)` | `timeout_ms: int` 或 `None` | `DeviceFeedback` | 查询激光编号。 |
| 发相机控制 | `CameraShmClient` | `lens_zoom_in(speed, timeout_ms=None)` | `speed: int`，范围 1-63；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 镜头变倍+。 |
| 发相机控制 | `CameraShmClient` | `lens_zoom_out(speed, timeout_ms=None)` | `speed: int`，范围 1-63；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 镜头变倍-。 |
| 发相机控制 | `CameraShmClient` | `lens_focus_plus(speed, timeout_ms=None)` | `speed: int`，范围 1-63；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 镜头聚焦+。 |
| 发相机控制 | `CameraShmClient` | `lens_focus_minus(speed, timeout_ms=None)` | `speed: int`，范围 1-63；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 镜头聚焦-。 |
| 发相机控制 | `CameraShmClient` | `lens_iris_plus(speed, timeout_ms=None)` | `speed: int`，范围 1-63；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 镜头光圈+。 |
| 发相机控制 | `CameraShmClient` | `lens_iris_minus(speed, timeout_ms=None)` | `speed: int`，范围 1-63；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 镜头光圈-。 |
| 发相机控制 | `CameraShmClient` | `lens_relay_on(relay_id, timeout_ms=None)` | `relay_id: int`，范围 1-8；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 打开指定镜头继电器。 |
| 发相机控制 | `CameraShmClient` | `lens_relay_off(relay_id, timeout_ms=None)` | `relay_id: int`，范围 1-8；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 关闭指定镜头继电器。 |
| 发相机控制 | `CameraShmClient` | `lens_set_preset(preset_id, timeout_ms=None)` | `preset_id: int`，范围 1-255；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 设置指定镜头预置位。 |
| 发相机控制 | `CameraShmClient` | `lens_call_preset(preset_id, timeout_ms=None)` | `preset_id: int`，范围 1-255；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 调用指定镜头预置位。 |
| 发相机控制 | `CameraShmClient` | `lens_query_zoom(timeout_ms=None)` | `timeout_ms: int` 或 `None` | `DeviceFeedback` | 查询镜头变倍位置。 |
| 发相机控制 | `CameraShmClient` | `lens_query_focus(timeout_ms=None)` | `timeout_ms: int` 或 `None` | `DeviceFeedback` | 查询镜头聚焦位置。 |
| 发相机控制 | `CameraShmClient` | `lens_query_iris(timeout_ms=None)` | `timeout_ms: int` 或 `None` | `DeviceFeedback` | 查询镜头光圈位置。 |
| 发相机控制 | `CameraShmClient` | `lens_goto_zoom(position, timeout_ms=None)` | `position: int`，范围 0-65535；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 控制镜头变倍到指定位置。 |
| 发相机控制 | `CameraShmClient` | `lens_goto_focus(position, timeout_ms=None)` | `position: int`，范围 0-65535；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 控制镜头聚焦到指定位置。 |
| 发相机控制 | `CameraShmClient` | `lens_goto_iris(position, timeout_ms=None)` | `position: int`，范围 0-65535；`timeout_ms: int` 或 `None` | `DeviceFeedback` | 控制镜头光圈到指定位置。 |
| 发相机控制 | `CameraShmClient` | `lens_stop(timeout_ms=None)` | `timeout_ms: int` 或 `None` | `DeviceFeedback` | 停止镜头当前动作。 |
