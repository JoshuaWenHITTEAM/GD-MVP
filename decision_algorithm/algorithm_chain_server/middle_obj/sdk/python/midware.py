import ctypes
import os
import struct

TYPE_HIGH_FREQ = 0
TYPE_LOW_FREQ = 1
TYPE_IMAGE_FRAME = 2
TYPE_RDMA_IMAGE_RAW = 3
TYPE_CONTROL_COMMAND = 255

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

_lib.midware_shm_producer_init.argtypes = [ctypes.c_char_p, ctypes.c_uint64]
_lib.midware_shm_producer_init.restype = ctypes.POINTER(MidwareShmCtx)

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
    Zero-Copy SHM Producer.
    
    Uses slot-based architecture compatible with Java ZeroCopySharedMemory.
    The capacity parameter specifies the maximum packet size (slot size).
    Internally uses 32 slots for zero-copy transmission.
    """
    def __init__(self, path: str, capacity: int, create_dirs=True):
        """
        Initialize a zero-copy SHM producer.
        
        Args:
            path: Path to the shared memory file (e.g., "/dev/shm/my_stream")
            capacity: Maximum packet size in bytes (slot size)
            create_dirs: If True, create parent directories if they don't exist
        """
        if create_dirs:
            dirs = os.path.dirname(path)
            if dirs and not os.path.exists(dirs):
                os.makedirs(dirs)
        
        self._ctx = _lib.midware_shm_producer_init(path.encode('utf-8'), capacity)
        if not self._ctx:
            raise RuntimeError(f"Failed to initialize SHM producer at {path}")

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
    
    Connects to an existing zero-copy SHM created by a producer.
    Uses slot-based architecture compatible with Java ZeroCopySharedMemory.
    """
    def __init__(self, path: str):
        """
        Initialize a zero-copy SHM consumer.
        
        Args:
            path: Path to the existing shared memory file
        """
        self._ctx = None # Initialize first
        if not os.path.exists(path):
            raise FileNotFoundError(f"SHM file not found: {path}")
            
        self._ctx = _lib.midware_shm_consumer_init(path.encode('utf-8'))
        if not self._ctx:
            raise RuntimeError(f"Failed to initialize SHM consumer at {path}")
            
        # Internal buffer for reuse (start with 64KB)
        self._buffer = ctypes.create_string_buffer(65536)

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

    def read_latest_packet(self):
        """
        Reads and parses the latest packet, dropping older packets.
        Returns PacketObj or None.
        """
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

    def __del__(self):
        self.close()
