import unittest
import time
import os
import threading
from midware import (
    ShmProducer,
    ShmConsumer,
    PacketObj,
    serialize_packet,
    parse_packet,
    rebuild_rdma_image,
    rebuild_rdma_image_from_packet,
    TYPE_RDMA_IMAGE_RAW,
    RDMA_IMAGE_SLICES,
    RDMA_IMAGE_SLICE_SIZE,
    RDMA_IMAGE_SLICE_HEADER_SIZE,
    RDMA_IMAGE_SLICE_PAYLOAD_SIZE,
    RDMA_IMAGE_RAW_SIZE,
    RDMA_IMAGE_REBUILT_SIZE,
)

SHM_PATH = "/dev/shm/test_py_sdk_shm"
CAPACITY = 1024 * 1024

class TestMidwareShm(unittest.TestCase):
    def setUp(self):
        # Clean previous
        if os.path.exists(SHM_PATH):
            os.remove(SHM_PATH)

    def tearDown(self):
        if os.path.exists(SHM_PATH):
            os.remove(SHM_PATH)

    def test_basic_rw(self):
        print("\n[PYTHON TEST] Init Producer...")
        producer = ShmProducer(SHM_PATH, CAPACITY)
        
        print("[PYTHON TEST] Init Consumer...")
        consumer = ShmConsumer(SHM_PATH)

        msg = b"Hello Python World"
        print(f"[PYTHON TEST] Writing: {msg}")
        self.assertTrue(producer.write(msg))

        print("[PYTHON TEST] Reading...")
        read_data = consumer.read()
        print(f"[PYTHON TEST] Read: {read_data}")
        
        self.assertEqual(read_data, msg)
        
        # Test empty read
        self.assertIsNone(consumer.read())
        print("[PYTHON TEST] Empty read verified.")

    def test_packet_rw(self):
        print("\n[PYTHON TEST] Packet Encapsulation Test...")
        pro = ShmProducer(SHM_PATH, CAPACITY)
        con = ShmConsumer(SHM_PATH)
        
        payload = b"PacketData"
        type_id = 99
        ts = 88888888
        
        pro.write_packet(payload, type_id, ts)
        
        pkt = con.read_packet()
        self.assertIsNotNone(pkt)
        self.assertEqual(pkt.type, type_id)
        self.assertEqual(pkt.timestamp_us, ts)
        self.assertEqual(pkt.payload, payload)
        
        print(f"[PYTHON TEST] Verified: {pkt}")

    def test_pure_packet_utils(self):
        print("\n[PYTHON TEST] Pure Packet Utils Test...")
        type_id = 42
        ts = 123000
        payload = b"PurePacketTest"
        
        # Serialize
        raw = serialize_packet(type_id, ts, payload)
        self.assertEqual(len(raw), 13 + len(payload))
        
        # Parse
        pkt = parse_packet(raw)
        self.assertIsNotNone(pkt)
        self.assertEqual(pkt.type, type_id)
        self.assertEqual(pkt.timestamp_us, ts)
        self.assertEqual(pkt.payload, payload)
        print("[PYTHON TEST] Pure serialize/parse verified.")

    def test_rebuild_rdma_image(self):
        raw = bytearray(RDMA_IMAGE_RAW_SIZE)
        base_index = 1000

        for logical_index in range(RDMA_IMAGE_SLICES):
            physical_index = RDMA_IMAGE_SLICES - logical_index - 1
            slice_start = physical_index * RDMA_IMAGE_SLICE_SIZE
            encoded_index = (base_index + logical_index) << 8
            raw[slice_start] = encoded_index & 0xFF
            raw[slice_start + 1] = (encoded_index >> 8) & 0xFF
            raw[slice_start + 2] = (encoded_index >> 16) & 0xFF
            payload_start = slice_start + RDMA_IMAGE_SLICE_HEADER_SIZE
            raw[payload_start:payload_start + RDMA_IMAGE_SLICE_PAYLOAD_SIZE] = (
                bytes([logical_index & 0xFF]) * RDMA_IMAGE_SLICE_PAYLOAD_SIZE
            )

        image = rebuild_rdma_image(raw)
        self.assertEqual(len(image), RDMA_IMAGE_REBUILT_SIZE)
        for logical_index in (0, 1, 255, 1024, RDMA_IMAGE_SLICES - 1):
            start = logical_index * RDMA_IMAGE_SLICE_PAYLOAD_SIZE
            self.assertEqual(image[start], logical_index & 0xFF)
            self.assertEqual(image[start + RDMA_IMAGE_SLICE_PAYLOAD_SIZE - 1], logical_index & 0xFF)

        packet = serialize_packet(TYPE_RDMA_IMAGE_RAW, 123456, bytes(raw))
        image_from_packet = rebuild_rdma_image_from_packet(packet)
        self.assertEqual(image_from_packet, image)
        print("\n[PYTHON TEST] RDMA image rebuild verified.")

    def test_large_data(self):
        producer = ShmProducer(SHM_PATH, CAPACITY)
        consumer = ShmConsumer(SHM_PATH)

        # 10KB data
        data = b"A" * 10240
        producer.write(data)
        read_data = consumer.read() # Auto-resizing should handle this
        self.assertEqual(len(read_data), 10240)
        self.assertEqual(read_data, data)
        print("\n[PYTHON TEST] Large data (10KB) rw verified.")
        
        # Very large data (> 64KB initial buffer)
        data2 = b"B" * 70000 
        producer.write(data2)
        read_data2 = consumer.read()
        self.assertEqual(len(read_data2), 70000)
        self.assertEqual(read_data2, data2)
        print("[PYTHON TEST] Very large data (70KB) rw verified (buffer resize).")


    def test_wrap_around(self):
        # Small capacity to force wrap around
        small_path = "/dev/shm/test_py_small"
        if os.path.exists(small_path):
            os.remove(small_path)
            
        pro = ShmProducer(small_path, 128) # small buffer
        con = ShmConsumer(small_path)

        # Write 60 bytes (header 4 + data 60 = 64). 128 total.
        # [Head: 0->64, Tail: 0]
        data1 = b"X" * 60
        pro.write(data1)
        
        # Read it to advance tail
        # [Head: 64, Tail: 0->64]
        self.assertEqual(con.read(), data1)
        
        # Write another 60 bytes
        # [Head: 64->128, Tail: 64]
        # Wait. 64 + 64 = 128. Capacity is 128 (header 64 + data start 64). 
        # Actually my capacity param is DATA capacity. Total file size is 64 + 128 = 192.
        # Ring buffer logic uses HEAD/TAIL purely modulo CAPACITY.
        # Head=64. Write 64 bytes. New Head -> 128. Wrap -> 0.
        # But wait, we store longs. 
        # Logical pos increases monotonically. 
        # get_pos = logical % cap.
        
        data2 = b"Y" * 60
        pro.write(data2)
        
        # Now buffer is logically fullish, but physically wrapped?
        # Let's write such that it splits.
        # Capacity 128.
        # Write 100 bytes.
        # Head 100.
        # Read 100. Tail 100.
        # Write 50 bytes. Start at 100. 100+50 = 150 > 128.
        # Should write 28 bytes at [100..127], 22 bytes at [0..21].
        
        # Clean up before changing capacity
        if os.path.exists(small_path):
            os.remove(small_path)

        pro = ShmProducer(small_path, 100) # Re-init
        con = ShmConsumer(small_path)
        
        # Write 80
        # Req: 84.
        d1 = b"1" * 80
        pro.write(d1)
        self.assertEqual(con.read(), d1)
        
        # Head=84, Tail=84. Cap=100.
        # Space starts at 84. Free=100.
        # Write 30 bytes.
        # Req=34.
        # Pos 84.. wrap at 100. Use 16 bytes at end, 18 bytes at start.
        d2 = b"2" * 30
        pro.write(d2)
        
        self.assertEqual(con.read(), d2)
        print("\n[PYTHON TEST] Wrap-around verified.")
        
        if os.path.exists(small_path):
            os.remove(small_path)

if __name__ == '__main__':
    unittest.main()
