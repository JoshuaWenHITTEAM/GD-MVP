import ctypes
import os
import socket
import struct
import sys
import time
from array import array
from dataclasses import dataclass
from pathlib import Path

_CURRENT_SDK_DIR = Path(__file__).resolve().parent
_PROJECT_SDK_DIR = _CURRENT_SDK_DIR.parents[4] / "sdk" / "python"
_ALLOWED_GENERATED_DIRS = {_CURRENT_SDK_DIR, _PROJECT_SDK_DIR}

_loaded_generated = sys.modules.get("midware_generated")
if _loaded_generated is not None:
    _loaded_generated_path = getattr(_loaded_generated, "__file__", None)
    if _loaded_generated_path and Path(_loaded_generated_path).resolve().parent not in _ALLOWED_GENERATED_DIRS:
        del sys.modules["midware_generated"]

for _sdk_path in reversed((_CURRENT_SDK_DIR, _PROJECT_SDK_DIR)):
    _sdk_path_str = str(_sdk_path)
    if _sdk_path.is_dir() and _sdk_path_str not in sys.path:
        sys.path.insert(0, _sdk_path_str)

from midware_generated import (
    COMMAND_CAMERA_LASER_APD_POWER_OFF,
    COMMAND_CAMERA_LASER_APD_POWER_ON,
    COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE,
    COMMAND_CAMERA_LASER_QUERY_ID,
    COMMAND_CAMERA_LASER_QUERY_SHOT_COUNT,
    COMMAND_CAMERA_LASER_SELF_TEST,
    COMMAND_CAMERA_LASER_SET_FARTHEST_DISTANCE,
    COMMAND_CAMERA_LASER_SET_NEAREST_DISTANCE,
    COMMAND_CAMERA_LASER_SET_WORK_TIMEOUT,
    COMMAND_CAMERA_LASER_SINGLE_MEASURE,
    COMMAND_CAMERA_LASER_STANDBY,
    COMMAND_CAMERA_LENS_CALL_PRESET,
    COMMAND_CAMERA_LENS_FOCUS_MINUS,
    COMMAND_CAMERA_LENS_FOCUS_PLUS,
    COMMAND_CAMERA_LENS_GOTO_FOCUS,
    COMMAND_CAMERA_LENS_GOTO_IRIS,
    COMMAND_CAMERA_LENS_GOTO_ZOOM,
    COMMAND_CAMERA_LENS_IRIS_MINUS,
    COMMAND_CAMERA_LENS_IRIS_PLUS,
    COMMAND_CAMERA_LENS_QUERY_FOCUS,
    COMMAND_CAMERA_LENS_QUERY_IRIS,
    COMMAND_CAMERA_LENS_QUERY_ZOOM,
    COMMAND_CAMERA_LENS_RELAY_OFF,
    COMMAND_CAMERA_LENS_RELAY_ON,
    COMMAND_CAMERA_LENS_SET_PRESET,
    COMMAND_CAMERA_LENS_STOP,
    COMMAND_CAMERA_LENS_ZOOM_IN,
    COMMAND_CAMERA_LENS_ZOOM_OUT,
    COMMAND_TURNTABLE_POSITION,
    COMMAND_SPECS,
    DEVICE_CAMERA,
    DEVICE_TURNTABLE,
)

TYPE_HIGH_FREQ = 0
TYPE_LOW_FREQ = 1
TYPE_IMAGE_FRAME = 2
TYPE_RDMA_IMAGE_RAW = 3
TYPE_DEVICE_FEEDBACK = 254
TYPE_CONTROL_COMMAND = 255

FEEDBACK_VERSION = 1
FEEDBACK_ACK = 1
FEEDBACK_RESPONSE = 2
FEEDBACK_EVENT = 3
FEEDBACK_ERROR = 4

STATUS_OK = 0
STATUS_UNSUPPORTED_DEVICE = 1
STATUS_UNSUPPORTED_COMMAND = 2
STATUS_INVALID_PARAM = 3
STATUS_HARDWARE_WRITE_FAILED = 4
STATUS_DEVICE_TIMEOUT = 5
STATUS_CHECKSUM_ERROR = 6
STATUS_DEVICE_ERROR = 7

DATA_NONE = 0x0000
DATA_RAW_DEVICE_FRAME = 0x0001
DATA_TEXT = 0x0002
DATA_TURNTABLE_STATE = 0x0101
DATA_CAMERA_LASER_MEASURE = 0x0201
DATA_CAMERA_LENS_POSITION = 0x0202
DATA_CAMERA_SELF_TEST = 0x0203
DATA_CAMERA_IDENTITY = 0x0204
DATA_CAMERA_LASER_RESPONSE = 0x0205

CONTROL_HEADER_SIZE = 4
FEEDBACK_HEADER_SIZE = 18

HEADER_SIZE = 13
DEFAULT_MAX_FRAME_LENGTH = 16 * 1024 * 1024

LOW_INT_QUAD_PROD_SHM_PATH = "/dev/shm/shm-prod-low-int-pair"
LOW_INT_QUAD_CONS_SHM_PATH = "/dev/shm/shm-cons-low-int-pair"
LOW_INT_QUAD_COUNT = 4
LOW_INT_QUAD_ITEM_SIZE = 4
LOW_INT_QUAD_PAYLOAD_SIZE = LOW_INT_QUAD_COUNT * LOW_INT_QUAD_ITEM_SIZE
LOW_INT_QUAD_SHM_CAPACITY = 64

RDMA_IMAGE_SLICES = 4096
RDMA_IMAGE_SLICE_SIZE = 264
RDMA_IMAGE_SLICE_HEADER_SIZE = 8
RDMA_IMAGE_SLICE_PAYLOAD_SIZE = RDMA_IMAGE_SLICE_SIZE - RDMA_IMAGE_SLICE_HEADER_SIZE
RDMA_IMAGE_RAW_SIZE = RDMA_IMAGE_SLICES * RDMA_IMAGE_SLICE_SIZE
RDMA_IMAGE_REBUILT_SIZE = RDMA_IMAGE_SLICES * RDMA_IMAGE_SLICE_PAYLOAD_SIZE

# Load the shared library
_lib_path = os.path.join(os.path.dirname(__file__), "../c/libmidware.so")
if not os.path.exists(_lib_path):
    raise RuntimeError(f"Shared library not found at {_lib_path}. Please build it first.")

_lib = ctypes.CDLL(_lib_path)

# Define C types
class MidwareShmCtx(ctypes.Structure):
    pass

_lib.midware_shm_writer_attach.argtypes = [ctypes.c_char_p, ctypes.c_uint64]
_lib.midware_shm_writer_attach.restype = ctypes.POINTER(MidwareShmCtx)

_lib.midware_shm_consumer_init.argtypes = [ctypes.c_char_p]
_lib.midware_shm_consumer_init.restype = ctypes.POINTER(MidwareShmCtx)

_lib.midware_shm_write.argtypes = [ctypes.POINTER(MidwareShmCtx), ctypes.c_void_p, ctypes.c_int32]
_lib.midware_shm_write.restype = ctypes.c_bool

_lib.midware_shm_read.argtypes = [ctypes.POINTER(MidwareShmCtx), ctypes.c_void_p, ctypes.c_int32]
_lib.midware_shm_read.restype = ctypes.c_int32

_lib.midware_shm_read_latest.argtypes = [ctypes.POINTER(MidwareShmCtx), ctypes.c_void_p, ctypes.c_int32]
_lib.midware_shm_read_latest.restype = ctypes.c_int32

_lib.midware_shm_peek_latest.argtypes = [ctypes.POINTER(MidwareShmCtx), ctypes.c_void_p, ctypes.c_int32]
_lib.midware_shm_peek_latest.restype = ctypes.c_int32

_lib.midware_shm_close.argtypes = [ctypes.POINTER(MidwareShmCtx)]
_lib.midware_shm_close.restype = None

# New Packet APIs
class Header(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_uint8),
        ("timestamp_us", ctypes.c_uint64),
        ("payload_len", ctypes.c_uint32)
    ]


class ShmBatchEntry(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.c_void_p),
        ("len", ctypes.c_int32),
        ("timestamp", ctypes.c_uint64),
        ("type", ctypes.c_uint8),
    ]


_lib.midware_packet_serialize.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint8, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_uint32]
_lib.midware_packet_serialize.restype = ctypes.c_int32

_lib.midware_shm_write_packet.argtypes = [ctypes.POINTER(MidwareShmCtx), ctypes.c_uint8, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_uint32]
_lib.midware_shm_write_packet.restype = ctypes.c_bool

_lib.midware_shm_read_packet.argtypes = [ctypes.POINTER(MidwareShmCtx), ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(Header), ctypes.POINTER(ctypes.c_void_p)]
_lib.midware_shm_read_packet.restype = ctypes.c_int32

_lib.midware_shm_read_latest_packet.argtypes = [ctypes.POINTER(MidwareShmCtx), ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(Header), ctypes.POINTER(ctypes.c_void_p)]
_lib.midware_shm_read_latest_packet.restype = ctypes.c_int32

_lib.midware_shm_peek_latest_packet.argtypes = [ctypes.POINTER(MidwareShmCtx), ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(Header), ctypes.POINTER(ctypes.c_void_p)]
_lib.midware_shm_peek_latest_packet.restype = ctypes.c_int32

_lib.midware_shm_peek_latest_batch.argtypes = [
    ctypes.POINTER(MidwareShmCtx),
    ctypes.POINTER(ShmBatchEntry),
    ctypes.c_int32,
    ctypes.c_bool,
]
_lib.midware_shm_peek_latest_batch.restype = ctypes.c_int32

_lib.midware_packet_parse.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(Header), ctypes.POINTER(ctypes.c_void_p)]
_lib.midware_packet_parse.restype = ctypes.c_bool

class PacketObj:
    def __init__(self, type_id, timestamp, payload):
        self.type = type_id
        self.timestamp_us = timestamp
        self.payload = payload

    def __repr__(self):
        return f"Packet(type={self.type}, ts={self.timestamp_us}, len={len(self.payload)})"

# Static Packet Utilities
def serialize_packet(type_id: int, timestamp_us: int, payload: bytes) -> bytes:
    """
    Serialize a packet into raw bytes compatible with the middleware protocol.
    """
    payload_len = len(payload)
    # Header overhead = 1 + 8 + 4 = 13 bytes
    total_len = 13 + payload_len
    
    buf = ctypes.create_string_buffer(total_len)
    res = _lib.midware_packet_serialize(buf, total_len, type_id, timestamp_us, payload, payload_len)
    
    if res <= 0:
        raise ValueError("Packet serialization failed")
        
    return buf.raw[:res]

def parse_packet(data: bytes) -> PacketObj:
    """
    Parse raw bytes into a PacketObj.
    Returns None if parsing fails (e.g. invalid length or format).
    """
    if not data:
        return None
        
    length = len(data)
    # create_string_buffer copies data, which is needed because C function expects void*
    # but more efficiently we can pass data directly if it's bytes
    
    header = Header()
    payload_ptr = ctypes.c_void_p()
    
    # We must ensure data is a ctypes compatible buffer or bytes
    # ctypes handles 'bytes' -> 'char*' conversion automatically for c_void_p? Not always for output.
    # But here input is const void*.
    
    valid = _lib.midware_packet_parse(data, length, ctypes.byref(header), ctypes.byref(payload_ptr))
    
    if valid:
        # Calculate payload offset
        # The payload_ptr is an address inside the 'data' buffer.
        # However, accessing 'bytes' object memory address in Python directly is tricky with moving GC.
        # But wait, we just want to extract the payload.
        # Python's midware_packet_parse binds to 'c_void_p' for buffer.
        # If we passed bytes, ctypes passes a pointer to the bytes content.
        # The returned payload_ptr is a raw address.
        # We can't easily map that back to an index in the bytes object without pointer arithmetic.
        
        # Simpler approach: Rely on known structure offset (13 bytes)
        # Verify payload length match
        p_len = header.payload_len
        if length < 13 + p_len:
            return None # Should have been caught by C parse
            
        # Manually slice
        # Ideally we trust C, but slicing "data[13 : 13+p_len]" is Pythonic and safe
        return PacketObj(header.type, header.timestamp_us, data[13 : 13+p_len])
        
    return None


@dataclass(frozen=True)
class ControlCommand:
    request_timestamp_us: int
    device_type: int
    command_type: int
    params: bytes


@dataclass(frozen=True)
class DeviceFeedback:
    version: int
    device_type: int
    subject_type: int
    feedback_kind: int
    status: int
    request_timestamp_us: int
    data_format: int
    data: bytes


FEEDBACK_KIND_NAMES = {
    FEEDBACK_ACK: "ACK",
    FEEDBACK_RESPONSE: "RESPONSE",
    FEEDBACK_EVENT: "EVENT",
    FEEDBACK_ERROR: "ERROR",
}

STATUS_NAMES = {
    STATUS_OK: "OK",
    STATUS_UNSUPPORTED_DEVICE: "UNSUPPORTED_DEVICE",
    STATUS_UNSUPPORTED_COMMAND: "UNSUPPORTED_COMMAND",
    STATUS_INVALID_PARAM: "INVALID_PARAM",
    STATUS_HARDWARE_WRITE_FAILED: "HARDWARE_WRITE_FAILED",
    STATUS_DEVICE_TIMEOUT: "DEVICE_TIMEOUT",
    STATUS_CHECKSUM_ERROR: "CHECKSUM_ERROR",
    STATUS_DEVICE_ERROR: "DEVICE_ERROR",
}

DATA_FORMAT_NAMES = {
    DATA_NONE: "NONE",
    DATA_RAW_DEVICE_FRAME: "RAW_DEVICE_FRAME",
    DATA_TEXT: "TEXT",
    DATA_TURNTABLE_STATE: "TURNTABLE_STATE",
    DATA_CAMERA_LASER_MEASURE: "CAMERA_LASER_MEASURE",
    DATA_CAMERA_LENS_POSITION: "CAMERA_LENS_POSITION",
    DATA_CAMERA_SELF_TEST: "CAMERA_SELF_TEST",
    DATA_CAMERA_IDENTITY: "CAMERA_IDENTITY",
    DATA_CAMERA_LASER_RESPONSE: "CAMERA_LASER_RESPONSE",
}


def _bytes_to_hex_inline(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def _camera_command_display(command_type: int) -> dict:
    spec = COMMAND_SPECS.get(DEVICE_CAMERA, {}).get(int(command_type), {})
    return {
        "key": spec.get("key", f"0x{int(command_type):04X}"),
        "name": spec.get("name", f"0x{int(command_type):04X}"),
    }


def parse_camera_feedback_data(data_format: int, data: bytes) -> dict:
    """
    Parse the camera-specific data field from a DeviceFeedback.

    Unknown or currently unsupported data formats are returned with rawHex/rawLen
    only. The function does not raise for short payloads; it leaves raw data
    available so callers can log or inspect it.
    """
    raw = bytes(data)
    parsed = {
        "rawHex": _bytes_to_hex_inline(raw),
        "rawLen": len(raw),
    }

    if data_format == DATA_NONE:
        return parsed

    if data_format == DATA_CAMERA_LASER_MEASURE and len(raw) >= 14:
        parsed.update({
            "laserCmd": f"0x{raw[0]:02X}",
            "measureStatus": raw[1],
            "distanceA": int.from_bytes(raw[2:6], "big"),
            "distanceB": int.from_bytes(raw[6:10], "big"),
            "distanceC": int.from_bytes(raw[10:14], "big"),
        })
        return parsed

    if data_format == DATA_CAMERA_LENS_POSITION and len(raw) >= 3:
        response_cmd = raw[0]
        lens_names = {
            0x5D: "zoom",
            0x5E: "focus",
            0x70: "iris",
        }
        parsed.update({
            "lensResponseCmd": f"0x{response_cmd:02X}",
            "lensPositionType": lens_names.get(response_cmd, "unknown"),
            "position": int.from_bytes(raw[1:3], "big"),
        })
        return parsed

    if data_format == DATA_CAMERA_SELF_TEST and len(raw) >= 1:
        parsed.update({
            "laserCmd": f"0x{raw[0]:02X}",
            "selfTestBytes": _bytes_to_hex_inline(raw[1:]),
        })
        if len(raw) >= 9:
            parsed.update({
                "minus5vCentivolt": int.from_bytes(raw[1:3], "big"),
                "nearestDistanceM": int.from_bytes(raw[3:5], "big"),
                "apdVoltageV": raw[5],
                "driveVoltageDecivolt": raw[6],
                "plus5vCentivolt": int.from_bytes(raw[7:9], "big"),
            })
        return parsed

    if data_format == DATA_CAMERA_IDENTITY and len(raw) >= 1:
        body = raw[1:]
        ascii_text = "".join(chr(b) if 32 <= b <= 126 else "." for b in body)
        parsed.update({
            "laserCmd": f"0x{raw[0]:02X}",
            "identityHex": _bytes_to_hex_inline(body),
            "identityAscii": ascii_text,
        })
        return parsed

    if data_format == DATA_CAMERA_LASER_RESPONSE and len(raw) >= 2:
        data_len = raw[1]
        body = raw[2:2 + data_len]
        parsed.update({
            "laserCmd": f"0x{raw[0]:02X}",
            "dataLen": data_len,
            "dataHex": _bytes_to_hex_inline(body),
        })
        return parsed

    return parsed


def parse_camera_feedback(feedback: DeviceFeedback) -> dict:
    """
    Parse a camera DeviceFeedback into algorithm-facing fields.
    """
    command = _camera_command_display(feedback.subject_type)
    return {
        "deviceType": int(feedback.device_type),
        "subjectType": int(feedback.subject_type),
        "subjectKey": command["key"],
        "subjectName": command["name"],
        "feedbackKind": int(feedback.feedback_kind),
        "feedbackKindName": FEEDBACK_KIND_NAMES.get(
            feedback.feedback_kind,
            f"UNKNOWN({feedback.feedback_kind})",
        ),
        "status": int(feedback.status),
        "statusName": STATUS_NAMES.get(feedback.status, f"UNKNOWN({feedback.status})"),
        "requestTimestampUs": int(feedback.request_timestamp_us),
        "dataFormat": int(feedback.data_format),
        "dataFormatName": DATA_FORMAT_NAMES.get(
            feedback.data_format,
            f"UNKNOWN(0x{feedback.data_format:04X})",
        ),
        "data": parse_camera_feedback_data(feedback.data_format, feedback.data),
    }


def _command_spec(device_type: int, command_type: int):
    try:
        return COMMAND_SPECS[int(device_type)][int(command_type)]
    except KeyError as exc:
        raise ValueError(f"unknown command device_type=0x{device_type:04X} command_type=0x{command_type:04X}") from exc


def _param_value(params: dict, key: str):
    if key not in params:
        raise ValueError(f"missing parameter: {key}")
    return params[key]


def _validate_range(name: str, value, spec: dict):
    if "min" in spec and value < spec["min"]:
        raise ValueError(f"{name} must be >= {spec['min']}")
    if "max" in spec and value > spec["max"]:
        raise ValueError(f"{name} must be <= {spec['max']}")


def _encode_param(spec: dict, value) -> bytes:
    key = spec["key"]
    if "values" in spec:
        ivalue = int(value)
        if ivalue != value and not isinstance(value, bool):
            raise ValueError(f"{key} must be one of {sorted(spec['values'])}")
        if ivalue not in spec["values"]:
            raise ValueError(f"{key} must be one of {sorted(spec['values'])}")
        value = ivalue

    if "scale" in spec:
        numeric = float(value)
        _validate_range(key, numeric, spec)
        value = int(round(numeric * spec["scale"]))
    else:
        original = value
        value = int(value)
        if value != original and not isinstance(original, bool):
            raise ValueError(f"{key} must be an integer")
        _validate_range(key, value, spec)

    ptype = spec["type"]
    if ptype == "uint8":
        if value < 0 or value > 0xFF:
            raise ValueError(f"{key} must be in uint8 range")
        return struct.pack(">B", value)
    if ptype == "uint16_be":
        if value < 0 or value > 0xFFFF:
            raise ValueError(f"{key} must be in uint16 range")
        return struct.pack(">H", value)
    if ptype == "int32_be":
        if value < -(2**31) or value > 2**31 - 1:
            raise ValueError(f"{key} must be in int32 range")
        return struct.pack(">i", value)
    raise ValueError(f"unsupported parameter type: {ptype}")


def build_control_payload(device_type: int, command_type: int, **params) -> bytes:
    spec = _command_spec(device_type, command_type)
    encoded = bytearray(struct.pack(">HH", int(device_type), int(command_type)))
    for param_spec in spec.get("params", []):
        encoded.extend(_encode_param(param_spec, _param_value(params, param_spec["key"])))
    extra = set(params) - {p["key"] for p in spec.get("params", [])}
    if extra:
        raise ValueError(f"unexpected parameter(s): {', '.join(sorted(extra))}")
    return bytes(encoded)


def parse_control_payload(payload: bytes, request_timestamp_us: int = 0) -> ControlCommand:
    raw = bytes(payload)
    if len(raw) < CONTROL_HEADER_SIZE:
        raise ValueError("control payload must be at least 4 bytes")
    device_type, command_type = struct.unpack_from(">HH", raw, 0)
    return ControlCommand(request_timestamp_us, device_type, command_type, raw[CONTROL_HEADER_SIZE:])


def build_control_packet(device_type: int, command_type: int, timestamp_us: int | None = None, **params) -> bytes:
    if timestamp_us is None:
        timestamp_us = time.time_ns() // 1000
    payload = build_control_payload(device_type, command_type, **params)
    return serialize_packet(TYPE_CONTROL_COMMAND, timestamp_us, payload)


def build_feedback_payload(
    device_type: int,
    subject_type: int,
    feedback_kind: int,
    status: int,
    request_timestamp_us: int,
    data_format: int = DATA_NONE,
    data: bytes = b"",
) -> bytes:
    body = bytes(data)
    return (
        struct.pack(
            ">BHHBHQH",
            FEEDBACK_VERSION,
            int(device_type),
            int(subject_type),
            int(feedback_kind),
            int(status),
            int(request_timestamp_us),
            int(data_format),
        )
        + body
    )


def parse_feedback_payload(payload: bytes) -> DeviceFeedback:
    raw = bytes(payload)
    if len(raw) < FEEDBACK_HEADER_SIZE:
        raise ValueError("feedback payload is shorter than DeviceFeedbackPayloadV1 header")
    version, device_type, subject_type, feedback_kind, status, request_ts, data_format = struct.unpack_from(
        ">BHHBHQH", raw, 0
    )
    if version != FEEDBACK_VERSION:
        raise ValueError(f"unsupported feedback version: {version}")
    return DeviceFeedback(
        version,
        device_type,
        subject_type,
        feedback_kind,
        status,
        request_ts,
        data_format,
        raw[FEEDBACK_HEADER_SIZE:],
    )


def build_feedback_packet(
    device_type: int,
    subject_type: int,
    feedback_kind: int,
    status: int,
    request_timestamp_us: int,
    data_format: int = DATA_NONE,
    data: bytes = b"",
    timestamp_us: int | None = None,
) -> bytes:
    if timestamp_us is None:
        timestamp_us = time.time_ns() // 1000
    payload = build_feedback_payload(
        device_type,
        subject_type,
        feedback_kind,
        status,
        request_timestamp_us,
        data_format,
        data,
    )
    return serialize_packet(TYPE_DEVICE_FEEDBACK, timestamp_us, payload)


def _timeout_seconds(timeout_ms: int):
    if timeout_ms is None or timeout_ms < 0:
        return None
    return timeout_ms / 1000.0


def _deadline(timeout_ms: int):
    if timeout_ms is None or timeout_ms < 0:
        return None
    return time.monotonic() + timeout_ms / 1000.0


def _remaining_timeout(deadline):
    if deadline is None:
        return None
    remaining = deadline - time.monotonic()
    return max(0.0, remaining)


def _feedback_matches_request(fb: DeviceFeedback, request_timestamp_us: int, subject_type: int | None) -> bool:
    if fb.request_timestamp_us == request_timestamp_us:
        return subject_type is None or fb.subject_type == subject_type
    if fb.request_timestamp_us == 0 and subject_type is not None:
        return fb.subject_type == subject_type
    return False


def _packet_total_length(data: bytes) -> int:
    if len(data) < HEADER_SIZE:
        raise ValueError("packet is shorter than middleware header")
    payload_len = struct.unpack_from(">I", data, 9)[0]
    return HEADER_SIZE + payload_len


def _validate_packet_bytes(data: bytes, max_frame_length: int = DEFAULT_MAX_FRAME_LENGTH) -> bytes:
    raw = bytes(data)
    total_len = _packet_total_length(raw)
    if total_len > max_frame_length:
        raise ValueError(f"packet length {total_len} exceeds max_frame_length {max_frame_length}")
    if len(raw) != total_len:
        raise ValueError(f"packet length mismatch: expected {total_len}, got {len(raw)}")
    if parse_packet(raw) is None:
        raise ValueError("invalid middleware packet")
    return raw


def rebuild_rdma_image(raw_slices: bytes) -> bytes:
    """
    Rebuild a raw RDMA image slice payload into pure image bytes.

    Args:
        raw_slices: 4096 slices x 264 bytes. Each slice has an 8-byte header
            followed by 256 bytes of image payload.

    Returns:
        Pure rebuilt image bytes (4096 x 256 bytes), without a middleware header.
    """
    raw = memoryview(raw_slices).cast("B")
    if len(raw) != RDMA_IMAGE_RAW_SIZE:
        raise ValueError(f"raw_slices must be {RDMA_IMAGE_RAW_SIZE} bytes, got {len(raw)}")

    indices = [0] * RDMA_IMAGE_SLICES
    min_index = None

    for i in range(RDMA_IMAGE_SLICES):
        base = i * RDMA_IMAGE_SLICE_SIZE
        index = (raw[base] | (raw[base + 1] << 8) | (raw[base + 2] << 16)) >> 8
        indices[i] = index
        if min_index is None or index < min_index:
            min_index = index

    image = bytearray(RDMA_IMAGE_REBUILT_SIZE)
    for i, index in enumerate(indices):
        normalized = index - min_index
        if normalized < 0 or normalized >= RDMA_IMAGE_SLICES:
            continue

        src_start = i * RDMA_IMAGE_SLICE_SIZE + RDMA_IMAGE_SLICE_HEADER_SIZE
        dst_start = normalized * RDMA_IMAGE_SLICE_PAYLOAD_SIZE
        image[dst_start:dst_start + RDMA_IMAGE_SLICE_PAYLOAD_SIZE] = (
            raw[src_start:src_start + RDMA_IMAGE_SLICE_PAYLOAD_SIZE]
        )

    return bytes(image)


def rebuild_rdma_image_from_packet(data: bytes) -> bytes:
    """
    Parse a type=3 middleware packet and rebuild its payload into pure image bytes.
    """
    pkt = parse_packet(data)
    if pkt is None:
        raise ValueError("invalid middleware packet")
    if pkt.type != TYPE_RDMA_IMAGE_RAW:
        raise ValueError(f"expected type={TYPE_RDMA_IMAGE_RAW}, got {pkt.type}")
    return rebuild_rdma_image(pkt.payload)


class ShmProducer:
    """
    Attach-only zero-copy SHM writer.
    
    This class does not create, resize, or initialize the SHM file. The
    middleware must create the SHM first. `capacity` is the maximum packet size
    the caller may write; attach fails if the existing slot size is smaller.
    """
    def __init__(self, path: str, capacity: int, create_dirs=True):
        """
        Attach to an existing zero-copy SHM writer endpoint.
        
        Args:
            path: Path to the shared memory file (e.g., "/dev/shm/my_stream")
            capacity: Maximum packet size in bytes required by the writer
            create_dirs: Deprecated and ignored; writers never create paths
        """
        self._ctx = _lib.midware_shm_writer_attach(path.encode('utf-8'), capacity)
        if not self._ctx:
            raise RuntimeError(f"Failed to attach SHM writer at {path}")

    def write(self, data: bytes) -> bool:
        return _lib.midware_shm_write(self._ctx, data, len(data))

    def write_packet(self, data: bytes, type_id: int = 0, timestamp_us: int = 0) -> bool:
        return _lib.midware_shm_write_packet(self._ctx, type_id, timestamp_us, data, len(data))

    def close(self):
        if self._ctx:
            _lib.midware_shm_close(self._ctx)
            self._ctx = None

    def __del__(self):
        self.close()

class ShmConsumer:
    """
    Zero-Copy SHM Consumer.
    
    Connects to an existing middleware-created zero-copy SHM when data is read.
    Uses slot-based architecture compatible with Java ZeroCopySharedMemory.
    """
    def __init__(self, path: str):
        """
        Initialize a zero-copy SHM consumer.
        
        Args:
            path: Path to the existing shared memory file
        """
        self.path = path
        self._ctx = None
        self._stat_key = None
        # Internal buffer for reuse (start with 64KB)
        self._buffer = ctypes.create_string_buffer(65536)
        self._ensure_open()

    def _current_stat_key(self):
        try:
            st = os.stat(self.path)
            return (st.st_dev, st.st_ino)
        except FileNotFoundError:
            return None

    def _ensure_open(self) -> bool:
        if self._ctx:
            current_key = self._current_stat_key()
            if current_key == self._stat_key:
                return True
            self.close()

        current_key = self._current_stat_key()
        if current_key is None:
            return False

        self._ctx = _lib.midware_shm_consumer_init(self.path.encode('utf-8'))
        if not self._ctx:
            raise RuntimeError(f"Failed to initialize SHM consumer at {self.path}")
        self._stat_key = current_key
        return True

    def read(self):
        """
        Reads next packet.
        Returns bytes if data available.
        Returns None if no data.
        Smartly handles resizing internal buffer if packet is too large.
        """
        # Try with current buffer size
        # If result > max_len, it means buffer was too small and result is REQUIRED size.
        # If result <= max_len, it means success and result is ACTUAL size.
        if not self._ensure_open():
            return None

        current_len = len(self._buffer)
        res = _lib.midware_shm_read(self._ctx, self._buffer, current_len)
        
        if res == 0:
            return None # Empty
            
        # Check if resize needed (Peek mode detected)
        if res > current_len:
            # Resize logic: Allocate exact needed size
            # (Or could use exponential growth like max(res, current_len * 2))
            self._buffer = ctypes.create_string_buffer(res)
            
            # Retry read with new buffer
            res = _lib.midware_shm_read(self._ctx, self._buffer, res)
            
            # Should not fail now unless concurrent reader messed up, 
            # or SHM closed, or weird corruption. 
            if res <= 0: 
                return None 

        if res < 0:
             # Should not happen with new C logic unless other errors
            raise ValueError(f"Unknown SHM error. code={res}")
        
        return self._buffer.raw[:res]

    def read_packet(self):
        """
        Reads and parses next packet.
        Returns PacketObj or None.
        """
        if not self._ensure_open():
            return None

        # Try with current buffer size
        current_len = len(self._buffer)
        header = Header()
        payload_ptr = ctypes.c_void_p()
        
        # Call C high-level API
        res = _lib.midware_shm_read_packet(self._ctx, self._buffer, current_len, ctypes.byref(header), ctypes.byref(payload_ptr))
        
        if res == 0:
            return None
            
        if res > current_len:
            # Buffer too small, resize and retry
            self._buffer = ctypes.create_string_buffer(res)
            res = _lib.midware_shm_read_packet(self._ctx, self._buffer, res, ctypes.byref(header), ctypes.byref(payload_ptr))
            
        if res > 0:
            # Calculate payload offset from pointer
            # payload_ptr is a void* address. We need to copy bytes from it.
            # Efficient method: slice from buffer since we know offset
            # Header size is 1+8+4 = 13 bytes.
            p_len = header.payload_len
            
            # Using raw buffer slice. 
            # Note: payload_ptr address returned by C is inside self._buffer.
            # We can just trust strict offset 13 if implementation is consistent, 
            # but using the C pointer is safer if structure changes? 
            # Actually C function returns pointer into buffer.
            # Let's stick to simple offset for ctypes simplicity or cast pointer.
            
            # Since midware_packet_parse returns pointer into buffer:
            offset = payload_ptr.value - ctypes.addressof(self._buffer)
            if offset < 0 or offset >= res:
                # Fallback to hardcoded offset if pointer math weirdness (shouldn't happen)
                offset = 13
                
            return PacketObj(header.type, header.timestamp_us, self._buffer.raw[offset : offset+p_len])
            
        return None

    def read_latest(self):
        """
        Reads latest packet bytes, dropping older packets.
        Returns bytes if data available, None if no data.
        """
        if not self._ensure_open():
            return None

        current_len = len(self._buffer)
        res = _lib.midware_shm_read_latest(self._ctx, self._buffer, current_len)

        if res == 0:
            return None

        if res > current_len:
            self._buffer = ctypes.create_string_buffer(res)
            res = _lib.midware_shm_read_latest(self._ctx, self._buffer, res)
            if res <= 0:
                return None

        if res < 0:
            raise ValueError(f"Unknown SHM error. code={res}")

        return self._buffer.raw[:res]

    def peek_latest(self):
        """
        Reads latest packet bytes without consuming it.
        Returns bytes if data available, None if no data.
        """
        if not self._ensure_open():
            return None

        current_len = len(self._buffer)
        res = _lib.midware_shm_peek_latest(self._ctx, self._buffer, current_len)

        if res == 0:
            return None

        if res > current_len:
            self._buffer = ctypes.create_string_buffer(res)
            res = _lib.midware_shm_peek_latest(self._ctx, self._buffer, res)
            if res <= 0:
                return None

        if res < 0:
            raise ValueError(f"Unknown SHM error. code={res}")

        return self._buffer.raw[:res]

    def peek_latest_batch(self, count: int = 2, parse_headers: bool = False):
        """
        Peeks the latest `count` raw entries without consuming them.
        Returns entries oldest-to-newest among the selected latest packets.
        """
        if count <= 0:
            return []
        if not self._ensure_open():
            return []

        entries = (ShmBatchEntry * count)()
        res = _lib.midware_shm_peek_latest_batch(self._ctx, entries, count, parse_headers)

        if res < 0:
            raise ValueError(f"Unknown SHM error. code={res}")
        if res == 0:
            return []

        packets = []
        for i in range(res):
            entry = entries[i]
            if entry.data and entry.len > 0:
                packets.append(ctypes.string_at(entry.data, entry.len))
        return packets

    def peek_latest_packets(self, count: int = 2):
        """
        Peeks the latest `count` middleware packets without consuming them.
        Returns PacketObj values oldest-to-newest among the selected latest packets.
        """
        packets = []
        for raw in self.peek_latest_batch(count, parse_headers=False):
            pkt = parse_packet(raw)
            if pkt is not None:
                packets.append(pkt)
        return packets

    def read_latest_packet(self):
        """
        Reads and parses the latest packet, dropping older packets.
        Returns PacketObj or None.
        """
        if not self._ensure_open():
            return None

        current_len = len(self._buffer)
        header = Header()
        payload_ptr = ctypes.c_void_p()

        res = _lib.midware_shm_read_latest_packet(self._ctx, self._buffer, current_len, ctypes.byref(header), ctypes.byref(payload_ptr))

        if res == 0:
            return None

        if res > current_len:
            self._buffer = ctypes.create_string_buffer(res)
            res = _lib.midware_shm_read_latest_packet(self._ctx, self._buffer, res, ctypes.byref(header), ctypes.byref(payload_ptr))

        if res > 0:
            p_len = header.payload_len
            offset = payload_ptr.value - ctypes.addressof(self._buffer)
            if offset < 0 or offset >= res:
                offset = 13
            return PacketObj(header.type, header.timestamp_us, self._buffer.raw[offset : offset+p_len])

        return None

    def peek_latest_packet(self):
        """
        Reads and parses the latest packet without consuming it.
        Returns PacketObj or None.
        """
        if not self._ensure_open():
            return None

        current_len = len(self._buffer)
        header = Header()
        payload_ptr = ctypes.c_void_p()

        res = _lib.midware_shm_peek_latest_packet(self._ctx, self._buffer, current_len, ctypes.byref(header), ctypes.byref(payload_ptr))

        if res == 0:
            return None

        if res > current_len:
            self._buffer = ctypes.create_string_buffer(res)
            res = _lib.midware_shm_peek_latest_packet(self._ctx, self._buffer, res, ctypes.byref(header), ctypes.byref(payload_ptr))

        if res > 0:
            p_len = header.payload_len
            offset = payload_ptr.value - ctypes.addressof(self._buffer)
            if offset < 0 or offset >= res:
                offset = 13
            return PacketObj(header.type, header.timestamp_us, self._buffer.raw[offset : offset+p_len])

        return None

    def close(self):
        if self._ctx:
            _lib.midware_shm_close(self._ctx)
            self._ctx = None
        self._stat_key = None

    def __del__(self):
        self.close()


def _low_int_quad_array(values):
    values = list(values)
    if len(values) != LOW_INT_QUAD_COUNT:
        raise ValueError("values must contain exactly four integers")

    quad = array("i", values)
    if quad.itemsize != LOW_INT_QUAD_ITEM_SIZE:
        raise RuntimeError(f"native int itemsize is {quad.itemsize}, expected 4")
    return quad


def _encode_low_int_quad(values) -> bytes:
    return _low_int_quad_array(values).tobytes()


def _decode_low_int_quad_packet(pkt):
    if pkt is None:
        return None
    if pkt.type != TYPE_LOW_FREQ:
        raise ValueError(f"unexpected packet type: {pkt.type}")
    if len(pkt.payload) < LOW_INT_QUAD_PAYLOAD_SIZE:
        raise ValueError(f"payload too short: {len(pkt.payload)} < {LOW_INT_QUAD_PAYLOAD_SIZE}")

    quad = array("i")
    if quad.itemsize != LOW_INT_QUAD_ITEM_SIZE:
        raise RuntimeError(f"native int itemsize is {quad.itemsize}, expected 4")
    quad.frombytes(pkt.payload[:LOW_INT_QUAD_PAYLOAD_SIZE])
    return list(quad)


class LowIntQuadProducer:
    """
    Long-lived producer for a list of four native signed int values on the low-frequency SHM path.
    """
    def __init__(self, shm_path=LOW_INT_QUAD_PROD_SHM_PATH, capacity=LOW_INT_QUAD_SHM_CAPACITY):
        self.producer = ShmProducer(shm_path, capacity)

    def write(self, values, timestamp_us=None) -> bool:
        if timestamp_us is None:
            timestamp_us = time.time_ns() // 1000
        return self.producer.write_packet(_encode_low_int_quad(values), type_id=TYPE_LOW_FREQ, timestamp_us=timestamp_us)

    def close(self):
        producer = getattr(self, "producer", None)
        if producer is not None:
            producer.close()
            self.producer = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def __del__(self):
        self.close()


class LowIntQuadConsumer:
    """
    Long-lived consumer for a list of four native signed int values on the low-frequency SHM path.
    """
    def __init__(self, shm_path=LOW_INT_QUAD_CONS_SHM_PATH):
        self.consumer = ShmConsumer(shm_path)

    def peek(self):
        return _decode_low_int_quad_packet(self.consumer.peek_latest_packet())

    def read(self, latest=True):
        pkt = self.consumer.read_latest_packet() if latest else self.consumer.read_packet()
        return _decode_low_int_quad_packet(pkt)

    def close(self):
        consumer = getattr(self, "consumer", None)
        if consumer is not None:
            consumer.close()
            self.consumer = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def __del__(self):
        self.close()


def write_low_int_quad(values, shm_path=LOW_INT_QUAD_PROD_SHM_PATH, timestamp_us=None, capacity=LOW_INT_QUAD_SHM_CAPACITY):
    with LowIntQuadProducer(shm_path, capacity) as producer:
        return producer.write(values, timestamp_us=timestamp_us)


def peek_low_int_quad(shm_path=LOW_INT_QUAD_CONS_SHM_PATH):
    with LowIntQuadConsumer(shm_path) as consumer:
        return consumer.peek()


def read_low_int_quad(shm_path=LOW_INT_QUAD_CONS_SHM_PATH, latest=True):
    with LowIntQuadConsumer(shm_path) as consumer:
        return consumer.read(latest=latest)


LowIntListProducer = LowIntQuadProducer
LowIntListConsumer = LowIntQuadConsumer


def write_low_int_list(values, shm_path=LOW_INT_QUAD_PROD_SHM_PATH, timestamp_us=None, capacity=LOW_INT_QUAD_SHM_CAPACITY):
    return write_low_int_quad(values, shm_path=shm_path, timestamp_us=timestamp_us, capacity=capacity)


def peek_low_int_list(shm_path=LOW_INT_QUAD_CONS_SHM_PATH):
    return peek_low_int_quad(shm_path=shm_path)


def read_low_int_list(shm_path=LOW_INT_QUAD_CONS_SHM_PATH, latest=True):
    return read_low_int_quad(shm_path=shm_path, latest=latest)


class UdpProducer:
    """
    UDP producer for middleware packets or raw datagrams.

    One UDP datagram carries one complete middleware packet when using
    write_packet().
    """
    def __init__(self, host: str, port: int, bind_host: str = "0.0.0.0", bind_port: int = 0, timeout_ms: int = 1000):
        self.host = host
        self.port = port
        self.timeout_ms = timeout_ms
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.settimeout(_timeout_seconds(timeout_ms))
        self._sock.bind((bind_host, bind_port))

    def write(self, datagram: bytes):
        try:
            return self._sock.sendto(bytes(datagram), (self.host, self.port))
        except socket.timeout:
            return None

    def write_packet(self, payload: bytes, type_id: int = 0, timestamp_us: int = 0):
        return self.write(serialize_packet(type_id, timestamp_us, bytes(payload)))

    def close(self):
        if self._sock:
            self._sock.close()
            self._sock = None

    def __del__(self):
        self.close()


class UdpConsumer:
    """
    UDP consumer for middleware packets or raw datagrams.
    """
    def __init__(self, bind_host: str = "0.0.0.0", port: int = 0, timeout_ms: int = 1000, max_datagram_size: int = 65535):
        self.timeout_ms = timeout_ms
        self.max_datagram_size = max_datagram_size
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.settimeout(_timeout_seconds(timeout_ms))
        self._sock.bind((bind_host, port))

    @property
    def local_port(self) -> int:
        return self._sock.getsockname()[1]

    def read(self):
        try:
            data, _addr = self._sock.recvfrom(self.max_datagram_size)
            return data
        except socket.timeout:
            return None

    def read_packet(self):
        data = self.read()
        if data is None:
            return None
        pkt = parse_packet(data)
        if pkt is None:
            raise ValueError("invalid middleware packet")
        return pkt

    def close(self):
        if self._sock:
            self._sock.close()
            self._sock = None

    def __del__(self):
        self.close()


class TcpProducer:
    """
    TCP producer for complete middleware packets.

    TCP writes complete BinaryPacketSpec frames directly; no extra length prefix
    is added.
    """
    def __init__(self, host: str, port: int, timeout_ms: int = 1000, max_frame_length: int = DEFAULT_MAX_FRAME_LENGTH):
        self.host = host
        self.port = port
        self.timeout_ms = timeout_ms
        self.max_frame_length = max_frame_length
        self._sock = None

    def _connect(self):
        if self._sock is not None:
            return
        self._sock = socket.create_connection((self.host, self.port), timeout=_timeout_seconds(self.timeout_ms))
        self._sock.settimeout(_timeout_seconds(self.timeout_ms))

    def _close_socket(self):
        sock = self._sock
        self._sock = None
        if sock is not None:
            sock.close()

    def write_packet_bytes(self, raw_packet: bytes):
        raw = _validate_packet_bytes(raw_packet, self.max_frame_length)

        for attempt in range(2):
            try:
                self._connect()
                self._sock.sendall(raw)
                return len(raw)
            except socket.timeout:
                return None
            except OSError:
                self._close_socket()
                if attempt == 1:
                    raise
        return None

    def write_packet(self, payload: bytes, type_id: int = 0, timestamp_us: int = 0):
        return self.write_packet_bytes(serialize_packet(type_id, timestamp_us, bytes(payload)))

    def close(self):
        self._close_socket()

    def __del__(self):
        self.close()


class TcpPacketClient:
    """
    TCP client that can both write and read complete middleware packets.
    """
    def __init__(self, host: str, port: int, timeout_ms: int = 1000, max_frame_length: int = DEFAULT_MAX_FRAME_LENGTH):
        self.host = host
        self.port = port
        self.timeout_ms = timeout_ms
        self.max_frame_length = max_frame_length
        self._sock = None
        self._buffer = bytearray()

    def _connect(self):
        if self._sock is not None:
            return
        self._sock = socket.create_connection((self.host, self.port), timeout=_timeout_seconds(self.timeout_ms))
        self._sock.settimeout(_timeout_seconds(self.timeout_ms))
        self._buffer.clear()

    def connect(self):
        self._connect()

    def _close_socket(self):
        sock = self._sock
        self._sock = None
        self._buffer.clear()
        if sock is not None:
            sock.close()

    def write_packet_bytes(self, raw_packet: bytes):
        raw = _validate_packet_bytes(raw_packet, self.max_frame_length)
        for attempt in range(2):
            try:
                self._connect()
                self._sock.sendall(raw)
                return len(raw)
            except socket.timeout:
                return None
            except OSError:
                self._close_socket()
                if attempt == 1:
                    raise
        return None

    def write_packet(self, payload: bytes, type_id: int = 0, timestamp_us: int = 0):
        return self.write_packet_bytes(serialize_packet(type_id, timestamp_us, bytes(payload)))

    def _fill_buffer(self, min_len: int, deadline):
        while len(self._buffer) < min_len:
            timeout = _remaining_timeout(deadline)
            try:
                self._connect()
                self._sock.settimeout(timeout)
                chunk = self._sock.recv(max(4096, min_len - len(self._buffer)))
            except (socket.timeout, BlockingIOError):
                return False
            except OSError as exc:
                had_partial = bool(self._buffer)
                self._close_socket()
                if had_partial:
                    raise ConnectionError("TCP connection failed before a full packet was read") from exc
                continue

            if chunk:
                self._buffer.extend(chunk)
                continue

            had_partial = bool(self._buffer)
            self._close_socket()
            if had_partial:
                raise ConnectionError("TCP connection closed before a full packet was read")
            return False
        return True

    def read_packet_bytes(self):
        deadline = _deadline(self.timeout_ms)
        if not self._fill_buffer(HEADER_SIZE, deadline):
            return None
        total_len = _packet_total_length(self._buffer)
        if total_len > self.max_frame_length:
            self._close_socket()
            raise ValueError(f"packet length {total_len} exceeds max_frame_length {self.max_frame_length}")
        if not self._fill_buffer(total_len, deadline):
            return None
        raw = bytes(self._buffer[:total_len])
        del self._buffer[:total_len]
        return raw

    def read_packet(self):
        raw = self.read_packet_bytes()
        if raw is None:
            return None
        pkt = parse_packet(raw)
        if pkt is None:
            raise ValueError("invalid middleware packet")
        return pkt

    def close(self):
        self._close_socket()

    def __del__(self):
        self.close()


class TcpConsumer:
    """
    TCP consumer for complete middleware packets.

    This class listens locally and accepts connections from a middleware TCP
    sender. If a connection closes cleanly between packets, the next read accepts
    a new producer connection.
    """
    def __init__(self, bind_host: str = "0.0.0.0", port: int = 0, timeout_ms: int = 1000, max_frame_length: int = DEFAULT_MAX_FRAME_LENGTH):
        self.timeout_ms = timeout_ms
        self.max_frame_length = max_frame_length
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.settimeout(_timeout_seconds(timeout_ms))
        self._server.bind((bind_host, port))
        self._server.listen(16)
        self._conn = None
        self._buffer = bytearray()

    @property
    def local_port(self) -> int:
        return self._server.getsockname()[1]

    def _close_conn(self):
        conn = self._conn
        self._conn = None
        self._buffer.clear()
        if conn is not None:
            conn.close()

    def _accept(self, deadline):
        self._server.settimeout(_remaining_timeout(deadline))
        try:
            conn, _addr = self._server.accept()
        except (socket.timeout, BlockingIOError):
            return False
        conn.settimeout(_timeout_seconds(self.timeout_ms))
        self._conn = conn
        self._buffer.clear()
        return True

    def _ensure_conn(self, deadline):
        if self._conn is not None:
            return True
        return self._accept(deadline)

    def _fill_buffer(self, min_len: int, deadline):
        while len(self._buffer) < min_len:
            if not self._ensure_conn(deadline):
                return False

            timeout = _remaining_timeout(deadline)
            self._conn.settimeout(timeout)
            try:
                chunk = self._conn.recv(max(4096, min_len - len(self._buffer)))
            except (socket.timeout, BlockingIOError):
                return False
            except OSError as exc:
                had_partial = bool(self._buffer)
                self._close_conn()
                if had_partial:
                    raise ConnectionError("TCP connection failed before a full packet was read") from exc
                continue

            if chunk:
                self._buffer.extend(chunk)
                continue

            had_partial = bool(self._buffer)
            self._close_conn()
            if had_partial:
                raise ConnectionError("TCP connection closed before a full packet was read")
        return True

    def read_packet_bytes(self):
        deadline = _deadline(self.timeout_ms)

        if not self._fill_buffer(HEADER_SIZE, deadline):
            return None

        total_len = _packet_total_length(self._buffer)
        if total_len > self.max_frame_length:
            self._close_conn()
            raise ValueError(f"packet length {total_len} exceeds max_frame_length {self.max_frame_length}")

        if not self._fill_buffer(total_len, deadline):
            return None

        raw = bytes(self._buffer[:total_len])
        del self._buffer[:total_len]
        return raw

    def read_packet(self):
        raw = self.read_packet_bytes()
        if raw is None:
            return None
        pkt = parse_packet(raw)
        if pkt is None:
            raise ValueError("invalid middleware packet")
        return pkt

    def close(self):
        self._close_conn()
        if self._server:
            self._server.close()
            self._server = None

    def __del__(self):
        self.close()


class CameraClient:
    """
    Minimal camera control client using centralized middleware TCP endpoints.
    """
    def __init__(
        self,
        command_host: str,
        command_port: int,
        feedback_host: str,
        feedback_port: int,
        timeout_ms: int = 1000,
    ):
        self.command = TcpPacketClient(command_host, command_port, timeout_ms=timeout_ms)
        self.feedback = TcpPacketClient(feedback_host, feedback_port, timeout_ms=timeout_ms)
        self.timeout_ms = timeout_ms

    def _send_camera_command(self, command_type: int, timeout_ms: int | None = None, **params) -> DeviceFeedback:
        timestamp_us = time.time_ns() // 1000
        packet = build_control_packet(DEVICE_CAMERA, command_type, timestamp_us=timestamp_us, **params)
        self.feedback.connect()
        self.command.write_packet_bytes(packet)
        return self.wait_feedback(timestamp_us, command_type, timeout_ms=timeout_ms)

    def wait_feedback(
        self,
        request_timestamp_us: int,
        subject_type: int | None = None,
        timeout_ms: int | None = None,
    ) -> DeviceFeedback:
        original_timeout = self.feedback.timeout_ms
        if timeout_ms is not None:
            self.feedback.timeout_ms = timeout_ms
        try:
            deadline = _deadline(self.feedback.timeout_ms)
            while deadline is None or time.monotonic() <= deadline:
                if deadline is not None:
                    self.feedback.timeout_ms = int(max(0.0, deadline - time.monotonic()) * 1000)
                pkt = self.feedback.read_packet()
                if pkt is None:
                    break
                if pkt.type != TYPE_DEVICE_FEEDBACK:
                    continue
                fb = parse_feedback_payload(pkt.payload)
                if not _feedback_matches_request(fb, request_timestamp_us, subject_type):
                    continue
                return fb
        finally:
            self.feedback.timeout_ms = original_timeout
        raise TimeoutError(f"no device feedback for request_timestamp_us={request_timestamp_us}")

    @staticmethod
    def parse_feedback(feedback: DeviceFeedback) -> dict:
        return parse_camera_feedback(feedback)

    def read_feedback(self, timeout_ms: int | None = None) -> DeviceFeedback | None:
        original_timeout = self.feedback.timeout_ms
        if timeout_ms is not None:
            self.feedback.timeout_ms = timeout_ms
        try:
            deadline = _deadline(self.feedback.timeout_ms)
            while deadline is None or time.monotonic() <= deadline:
                if deadline is not None:
                    self.feedback.timeout_ms = int(max(0.0, deadline - time.monotonic()) * 1000)
                pkt = self.feedback.read_packet()
                if pkt is None:
                    return None
                if pkt.type != TYPE_DEVICE_FEEDBACK:
                    continue
                return parse_feedback_payload(pkt.payload)
        finally:
            self.feedback.timeout_ms = original_timeout
        return None

    def read_parsed_feedback(self, timeout_ms: int | None = None) -> dict | None:
        feedback = self.read_feedback(timeout_ms=timeout_ms)
        if feedback is None:
            return None
        return parse_camera_feedback(feedback)

    def laser_standby(self, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LASER_STANDBY, timeout_ms=timeout_ms)

    def laser_single_measure(self, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LASER_SINGLE_MEASURE, timeout_ms=timeout_ms)

    def laser_continuous_measure(self, period_ms: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(
            COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE,
            timeout_ms=timeout_ms,
            periodMs=period_ms,
        )

    def laser_self_test(self, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LASER_SELF_TEST, timeout_ms=timeout_ms)

    def laser_set_nearest_distance(self, distance_m: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(
            COMMAND_CAMERA_LASER_SET_NEAREST_DISTANCE,
            timeout_ms=timeout_ms,
            distanceM=distance_m,
        )

    def laser_query_shot_count(self, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LASER_QUERY_SHOT_COUNT, timeout_ms=timeout_ms)

    def laser_set_farthest_distance(self, distance_m: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(
            COMMAND_CAMERA_LASER_SET_FARTHEST_DISTANCE,
            timeout_ms=timeout_ms,
            distanceM=distance_m,
        )

    def laser_apd_power_on(self, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LASER_APD_POWER_ON, timeout_ms=timeout_ms)

    def laser_apd_power_off(self, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LASER_APD_POWER_OFF, timeout_ms=timeout_ms)

    def laser_set_work_timeout(self, timeout_min: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(
            COMMAND_CAMERA_LASER_SET_WORK_TIMEOUT,
            timeout_ms=timeout_ms,
            timeoutMin=timeout_min,
        )

    def laser_query_id(self, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LASER_QUERY_ID, timeout_ms=timeout_ms)

    def lens_zoom_in(self, speed: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LENS_ZOOM_IN, timeout_ms=timeout_ms, speed=speed)

    def lens_zoom_out(self, speed: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LENS_ZOOM_OUT, timeout_ms=timeout_ms, speed=speed)

    def lens_focus_plus(self, speed: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LENS_FOCUS_PLUS, timeout_ms=timeout_ms, speed=speed)

    def lens_focus_minus(self, speed: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LENS_FOCUS_MINUS, timeout_ms=timeout_ms, speed=speed)

    def lens_iris_plus(self, speed: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LENS_IRIS_PLUS, timeout_ms=timeout_ms, speed=speed)

    def lens_iris_minus(self, speed: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LENS_IRIS_MINUS, timeout_ms=timeout_ms, speed=speed)

    def lens_relay_on(self, relay_id: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(
            COMMAND_CAMERA_LENS_RELAY_ON,
            timeout_ms=timeout_ms,
            relayId=relay_id,
        )

    def lens_relay_off(self, relay_id: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(
            COMMAND_CAMERA_LENS_RELAY_OFF,
            timeout_ms=timeout_ms,
            relayId=relay_id,
        )

    def lens_set_preset(self, preset_id: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(
            COMMAND_CAMERA_LENS_SET_PRESET,
            timeout_ms=timeout_ms,
            presetId=preset_id,
        )

    def lens_call_preset(self, preset_id: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(
            COMMAND_CAMERA_LENS_CALL_PRESET,
            timeout_ms=timeout_ms,
            presetId=preset_id,
        )

    def lens_query_zoom(self, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LENS_QUERY_ZOOM, timeout_ms=timeout_ms)

    def lens_query_focus(self, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LENS_QUERY_FOCUS, timeout_ms=timeout_ms)

    def lens_query_iris(self, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LENS_QUERY_IRIS, timeout_ms=timeout_ms)

    def lens_goto_zoom(self, position: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LENS_GOTO_ZOOM, timeout_ms=timeout_ms, position=position)

    def lens_goto_focus(self, position: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LENS_GOTO_FOCUS, timeout_ms=timeout_ms, position=position)

    def lens_goto_iris(self, position: int, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LENS_GOTO_IRIS, timeout_ms=timeout_ms, position=position)

    def lens_stop(self, timeout_ms: int | None = None) -> DeviceFeedback:
        return self._send_camera_command(COMMAND_CAMERA_LENS_STOP, timeout_ms=timeout_ms)

    def close(self):
        self.command.close()
        self.feedback.close()

    def __del__(self):
        self.close()


class CameraShmClient(CameraClient):
    """
    Camera control client for the formal SHM + middleware TCP duplex path.
    """
    def __init__(
        self,
        command_shm_path: str,
        feedback_shm_path: str,
        command_capacity: int = 40960,
        timeout_ms: int = 1000,
    ):
        self.command = ShmProducer(command_shm_path, command_capacity)
        self.feedback = ShmConsumer(feedback_shm_path)
        self.timeout_ms = timeout_ms

    def _send_camera_command(self, command_type: int, timeout_ms: int | None = None, **params) -> DeviceFeedback:
        timestamp_us = time.time_ns() // 1000
        packet = build_control_packet(DEVICE_CAMERA, command_type, timestamp_us=timestamp_us, **params)
        if not self.command.write(packet):
            raise RuntimeError("failed to write camera command to SHM")
        return self.wait_feedback(timestamp_us, command_type, timeout_ms=timeout_ms)

    def wait_feedback(
        self,
        request_timestamp_us: int,
        subject_type: int | None = None,
        timeout_ms: int | None = None,
    ) -> DeviceFeedback:
        effective_timeout_ms = self.timeout_ms if timeout_ms is None else timeout_ms
        deadline = _deadline(effective_timeout_ms)

        while deadline is None or time.monotonic() <= deadline:
            pkt = self.feedback.read_packet()
            if pkt is None:
                time.sleep(0.001)
                continue
            if pkt.type != TYPE_DEVICE_FEEDBACK:
                continue
            fb = parse_feedback_payload(pkt.payload)
            if not _feedback_matches_request(fb, request_timestamp_us, subject_type):
                continue
            return fb

        raise TimeoutError(f"no device feedback for request_timestamp_us={request_timestamp_us}")

    def read_feedback(self, timeout_ms: int | None = None) -> DeviceFeedback | None:
        effective_timeout_ms = self.timeout_ms if timeout_ms is None else timeout_ms
        deadline = _deadline(effective_timeout_ms)

        while deadline is None or time.monotonic() <= deadline:
            pkt = self.feedback.read_packet()
            if pkt is None:
                time.sleep(0.001)
                continue
            if pkt.type != TYPE_DEVICE_FEEDBACK:
                continue
            return parse_feedback_payload(pkt.payload)

        return None

    def close(self):
        command = getattr(self, "command", None)
        if command is not None:
            command.close()
            self.command = None
        feedback = getattr(self, "feedback", None)
        if feedback is not None:
            feedback.close()
            self.feedback = None
