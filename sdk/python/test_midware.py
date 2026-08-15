import unittest
import ctypes
import time
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(__file__))

import midware as mw
from midware import (
    CameraClient,
    CameraShmClient,
    ControlCommand,
    DeviceFeedback,
    ShmProducer,
    ShmConsumer,
    UdpProducer,
    UdpConsumer,
    TcpProducer,
    TcpConsumer,
    PacketObj,
    build_control_packet,
    build_control_payload,
    build_feedback_packet,
    build_feedback_payload,
    parse_control_payload,
    parse_camera_feedback,
    parse_camera_feedback_data,
    parse_feedback_payload,
    serialize_packet,
    parse_packet,
    rebuild_rdma_image,
    rebuild_rdma_image_from_packet,
    DATA_NONE,
    DATA_CAMERA_LASER_MEASURE,
    DATA_CAMERA_LENS_POSITION,
    DATA_CAMERA_LASER_RESPONSE,
    DATA_TURNTABLE_STATE,
    DEVICE_CAMERA,
    DEVICE_TURNTABLE,
    COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE,
    COMMAND_CAMERA_LENS_QUERY_ZOOM,
    COMMAND_CAMERA_LENS_STOP,
    COMMAND_TURNTABLE_POSITION,
    FEEDBACK_ACK,
    FEEDBACK_RESPONSE,
    STATUS_INVALID_PARAM,
    STATUS_OK,
    TYPE_CONTROL_COMMAND,
    TYPE_DEVICE_FEEDBACK,
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


class _TestShmCtx(ctypes.Structure):
    pass


_test_lib_path = os.path.join(os.path.dirname(__file__), "../c/libmidware.so")
_test_lib = ctypes.CDLL(_test_lib_path)
_test_lib.midware_shm_producer_init.argtypes = [ctypes.c_char_p, ctypes.c_uint64]
_test_lib.midware_shm_producer_init.restype = ctypes.POINTER(_TestShmCtx)
_test_lib.midware_shm_close.argtypes = [ctypes.POINTER(_TestShmCtx)]
_test_lib.midware_shm_close.restype = None


def init_shm(path, capacity):
    ctx = _test_lib.midware_shm_producer_init(path.encode("utf-8"), capacity)
    if not ctx:
        raise RuntimeError(f"failed to initialize test SHM at {path}")
    _test_lib.midware_shm_close(ctx)

CAMERA_COMMAND_CASES = [
    ("laser_standby", (), mw.COMMAND_CAMERA_LASER_STANDBY, {}, "00 02 01 01"),
    ("laser_single_measure", (), mw.COMMAND_CAMERA_LASER_SINGLE_MEASURE, {}, "00 02 01 02"),
    (
        "laser_continuous_measure",
        (1000,),
        mw.COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE,
        {"periodMs": 1000},
        "00 02 01 03 03 E8",
    ),
    ("laser_self_test", (), mw.COMMAND_CAMERA_LASER_SELF_TEST, {}, "00 02 01 04"),
    (
        "laser_set_nearest_distance",
        (100,),
        mw.COMMAND_CAMERA_LASER_SET_NEAREST_DISTANCE,
        {"distanceM": 100},
        "00 02 01 05 00 64",
    ),
    ("laser_query_shot_count", (), mw.COMMAND_CAMERA_LASER_QUERY_SHOT_COUNT, {}, "00 02 01 06"),
    (
        "laser_set_farthest_distance",
        (5000,),
        mw.COMMAND_CAMERA_LASER_SET_FARTHEST_DISTANCE,
        {"distanceM": 5000},
        "00 02 01 07 13 88",
    ),
    ("laser_apd_power_on", (), mw.COMMAND_CAMERA_LASER_APD_POWER_ON, {}, "00 02 01 08"),
    ("laser_apd_power_off", (), mw.COMMAND_CAMERA_LASER_APD_POWER_OFF, {}, "00 02 01 09"),
    (
        "laser_set_work_timeout",
        (30,),
        mw.COMMAND_CAMERA_LASER_SET_WORK_TIMEOUT,
        {"timeoutMin": 30},
        "00 02 01 0A 00 1E",
    ),
    ("laser_query_id", (), mw.COMMAND_CAMERA_LASER_QUERY_ID, {}, "00 02 01 0B"),
    ("lens_zoom_in", (1,), mw.COMMAND_CAMERA_LENS_ZOOM_IN, {"speed": 1}, "00 02 02 01 01"),
    ("lens_zoom_out", (1,), mw.COMMAND_CAMERA_LENS_ZOOM_OUT, {"speed": 1}, "00 02 02 02 01"),
    ("lens_focus_plus", (1,), mw.COMMAND_CAMERA_LENS_FOCUS_PLUS, {"speed": 1}, "00 02 02 03 01"),
    ("lens_focus_minus", (1,), mw.COMMAND_CAMERA_LENS_FOCUS_MINUS, {"speed": 1}, "00 02 02 04 01"),
    ("lens_iris_plus", (1,), mw.COMMAND_CAMERA_LENS_IRIS_PLUS, {"speed": 1}, "00 02 02 05 01"),
    ("lens_iris_minus", (1,), mw.COMMAND_CAMERA_LENS_IRIS_MINUS, {"speed": 1}, "00 02 02 06 01"),
    ("lens_relay_on", (1,), mw.COMMAND_CAMERA_LENS_RELAY_ON, {"relayId": 1}, "00 02 02 07 01"),
    ("lens_relay_off", (1,), mw.COMMAND_CAMERA_LENS_RELAY_OFF, {"relayId": 1}, "00 02 02 08 01"),
    ("lens_set_preset", (1,), mw.COMMAND_CAMERA_LENS_SET_PRESET, {"presetId": 1}, "00 02 02 09 01"),
    ("lens_call_preset", (1,), mw.COMMAND_CAMERA_LENS_CALL_PRESET, {"presetId": 1}, "00 02 02 0A 01"),
    ("lens_query_zoom", (), mw.COMMAND_CAMERA_LENS_QUERY_ZOOM, {}, "00 02 02 0B"),
    ("lens_query_focus", (), mw.COMMAND_CAMERA_LENS_QUERY_FOCUS, {}, "00 02 02 0C"),
    ("lens_query_iris", (), mw.COMMAND_CAMERA_LENS_QUERY_IRIS, {}, "00 02 02 0D"),
    ("lens_goto_zoom", (0x1234,), mw.COMMAND_CAMERA_LENS_GOTO_ZOOM, {"position": 0x1234}, "00 02 02 0E 12 34"),
    ("lens_goto_focus", (0x1234,), mw.COMMAND_CAMERA_LENS_GOTO_FOCUS, {"position": 0x1234}, "00 02 02 0F 12 34"),
    ("lens_goto_iris", (0x1234,), mw.COMMAND_CAMERA_LENS_GOTO_IRIS, {"position": 0x1234}, "00 02 02 10 12 34"),
    ("lens_stop", (), mw.COMMAND_CAMERA_LENS_STOP, {}, "00 02 02 11"),
]

CAMERA_COMMAND_CONSTANTS = {
    "COMMAND_CAMERA_LASER_STANDBY": 0x0101,
    "COMMAND_CAMERA_LASER_SINGLE_MEASURE": 0x0102,
    "COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE": 0x0103,
    "COMMAND_CAMERA_LASER_SELF_TEST": 0x0104,
    "COMMAND_CAMERA_LASER_SET_NEAREST_DISTANCE": 0x0105,
    "COMMAND_CAMERA_LASER_QUERY_SHOT_COUNT": 0x0106,
    "COMMAND_CAMERA_LASER_SET_FARTHEST_DISTANCE": 0x0107,
    "COMMAND_CAMERA_LASER_APD_POWER_ON": 0x0108,
    "COMMAND_CAMERA_LASER_APD_POWER_OFF": 0x0109,
    "COMMAND_CAMERA_LASER_SET_WORK_TIMEOUT": 0x010A,
    "COMMAND_CAMERA_LASER_QUERY_ID": 0x010B,
    "COMMAND_CAMERA_LENS_ZOOM_IN": 0x0201,
    "COMMAND_CAMERA_LENS_ZOOM_OUT": 0x0202,
    "COMMAND_CAMERA_LENS_FOCUS_PLUS": 0x0203,
    "COMMAND_CAMERA_LENS_FOCUS_MINUS": 0x0204,
    "COMMAND_CAMERA_LENS_IRIS_PLUS": 0x0205,
    "COMMAND_CAMERA_LENS_IRIS_MINUS": 0x0206,
    "COMMAND_CAMERA_LENS_RELAY_ON": 0x0207,
    "COMMAND_CAMERA_LENS_RELAY_OFF": 0x0208,
    "COMMAND_CAMERA_LENS_SET_PRESET": 0x0209,
    "COMMAND_CAMERA_LENS_CALL_PRESET": 0x020A,
    "COMMAND_CAMERA_LENS_QUERY_ZOOM": 0x020B,
    "COMMAND_CAMERA_LENS_QUERY_FOCUS": 0x020C,
    "COMMAND_CAMERA_LENS_QUERY_IRIS": 0x020D,
    "COMMAND_CAMERA_LENS_GOTO_ZOOM": 0x020E,
    "COMMAND_CAMERA_LENS_GOTO_FOCUS": 0x020F,
    "COMMAND_CAMERA_LENS_GOTO_IRIS": 0x0210,
    "COMMAND_CAMERA_LENS_STOP": 0x0211,
}

class TestControlProtocol(unittest.TestCase):
    def test_camera_generated_constants_match_hardware_order(self):
        for name, expected in CAMERA_COMMAND_CONSTANTS.items():
            with self.subTest(name=name):
                self.assertEqual(getattr(mw, name), expected)

    def test_control_payload_camera_commands(self):
        payload = build_control_payload(
            DEVICE_CAMERA,
            COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE,
            periodMs=1000,
        )
        self.assertEqual(payload, bytes.fromhex("00 02 01 03 03 E8"))

        parsed = parse_control_payload(payload, request_timestamp_us=123456)
        self.assertEqual(
            parsed,
            ControlCommand(
                request_timestamp_us=123456,
                device_type=DEVICE_CAMERA,
                command_type=COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE,
                params=bytes.fromhex("03 E8"),
            ),
        )

        self.assertEqual(
            build_control_payload(DEVICE_CAMERA, COMMAND_CAMERA_LENS_STOP),
            bytes.fromhex("00 02 02 11"),
        )

    def test_control_payload_all_camera_commands(self):
        for method_name, _args, command_type, params, expected_hex in CAMERA_COMMAND_CASES:
            with self.subTest(method=method_name):
                payload = build_control_payload(DEVICE_CAMERA, command_type, **params)
                self.assertEqual(payload, bytes.fromhex(expected_hex))

    def test_control_payload_validation(self):
        with self.assertRaises(ValueError):
            build_control_payload(
                DEVICE_CAMERA,
                COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE,
                periodMs=65536,
            )
        with self.assertRaises(ValueError):
            build_control_payload(DEVICE_CAMERA, COMMAND_CAMERA_LENS_STOP, speed=1)
        with self.assertRaises(ValueError):
            build_control_payload(DEVICE_CAMERA, mw.COMMAND_CAMERA_LENS_ZOOM_IN, speed=0)
        with self.assertRaises(ValueError):
            build_control_payload(DEVICE_CAMERA, mw.COMMAND_CAMERA_LENS_ZOOM_IN, speed=64)
        with self.assertRaises(ValueError):
            build_control_payload(DEVICE_CAMERA, mw.COMMAND_CAMERA_LENS_RELAY_ON, relayId=0)
        with self.assertRaises(ValueError):
            build_control_payload(DEVICE_CAMERA, mw.COMMAND_CAMERA_LENS_RELAY_ON, relayId=9)
        with self.assertRaises(ValueError):
            build_control_payload(DEVICE_CAMERA, mw.COMMAND_CAMERA_LENS_SET_PRESET, presetId=0)

    def test_camera_client_methods_dispatch_expected_commands(self):
        client = CameraClient.__new__(CameraClient)
        client.command = type("NoopEndpoint", (), {"close": lambda self: None})()
        client.feedback = type("NoopEndpoint", (), {"close": lambda self: None})()
        calls = []

        def fake_send(command_type, timeout_ms=None, **params):
            calls.append((command_type, timeout_ms, params))
            return DeviceFeedback(1, DEVICE_CAMERA, command_type, FEEDBACK_ACK, STATUS_OK, 123, DATA_NONE, b"")

        client._send_camera_command = fake_send
        for method_name, args, command_type, params, _expected_hex in CAMERA_COMMAND_CASES:
            with self.subTest(method=method_name):
                feedback = getattr(client, method_name)(*args, timeout_ms=77)
                self.assertEqual(feedback.subject_type, command_type)
                self.assertEqual(calls[-1], (command_type, 77, params))

    def test_camera_shm_client_methods_dispatch_expected_commands(self):
        client = CameraShmClient.__new__(CameraShmClient)
        client.command = type("NoopEndpoint", (), {"close": lambda self: None})()
        client.feedback = type("NoopEndpoint", (), {"close": lambda self: None})()
        calls = []

        def fake_send(command_type, timeout_ms=None, **params):
            calls.append((command_type, timeout_ms, params))
            return DeviceFeedback(1, DEVICE_CAMERA, command_type, FEEDBACK_ACK, STATUS_OK, 123, DATA_NONE, b"")

        client._send_camera_command = fake_send
        for method_name, args, command_type, params, _expected_hex in CAMERA_COMMAND_CASES:
            with self.subTest(method=method_name):
                feedback = getattr(client, method_name)(*args, timeout_ms=77)
                self.assertEqual(feedback.subject_type, command_type)
                self.assertEqual(calls[-1], (command_type, 77, params))

    def test_camera_shm_client_writes_type255_packet(self):
        command_path = "/dev/shm/test_py_camera_command"
        feedback_path = "/dev/shm/test_py_camera_feedback"
        for path in (command_path, feedback_path):
            if os.path.exists(path):
                os.remove(path)

        init_shm(command_path, 40960)
        client = CameraShmClient(command_path, feedback_path, command_capacity=40960, timeout_ms=50)
        try:
            def fake_wait(request_timestamp_us, subject_type=None, timeout_ms=None):
                return DeviceFeedback(
                    1,
                    DEVICE_CAMERA,
                    subject_type,
                    FEEDBACK_ACK,
                    STATUS_OK,
                    request_timestamp_us,
                    DATA_NONE,
                    b"",
                )

            client.wait_feedback = fake_wait
            client.lens_stop(timeout_ms=10)

            consumer = ShmConsumer(command_path)
            pkt = consumer.read_packet()
            consumer.close()
            self.assertIsNotNone(pkt)
            self.assertEqual(pkt.type, TYPE_CONTROL_COMMAND)
            self.assertEqual(pkt.payload, build_control_payload(DEVICE_CAMERA, COMMAND_CAMERA_LENS_STOP))
        finally:
            client.close()
            for path in (command_path, feedback_path):
                if os.path.exists(path):
                    os.remove(path)

    def test_camera_shm_client_filters_feedback_by_timestamp(self):
        command_path = "/dev/shm/test_py_camera_command_filter"
        feedback_path = "/dev/shm/test_py_camera_feedback_filter"
        for path in (command_path, feedback_path):
            if os.path.exists(path):
                os.remove(path)

        init_shm(command_path, 40960)
        init_shm(feedback_path, 40960)
        client = CameraShmClient(command_path, feedback_path, command_capacity=40960, timeout_ms=100)
        producer = ShmProducer(feedback_path, 40960)
        try:
            producer.write(build_feedback_packet(
                DEVICE_CAMERA,
                COMMAND_CAMERA_LENS_STOP,
                FEEDBACK_ACK,
                STATUS_OK,
                request_timestamp_us=111,
                data_format=DATA_CAMERA_LASER_RESPONSE,
                data=b"\x01\x00",
            ))
            producer.write(build_feedback_packet(
                DEVICE_CAMERA,
                COMMAND_CAMERA_LENS_STOP,
                FEEDBACK_ACK,
                STATUS_OK,
                request_timestamp_us=222,
            ))

            feedback = client.wait_feedback(222, COMMAND_CAMERA_LENS_STOP, timeout_ms=100)
            self.assertEqual(feedback.request_timestamp_us, 222)
            self.assertEqual(feedback.status, STATUS_OK)
        finally:
            producer.close()
            client.close()
            for path in (command_path, feedback_path):
                if os.path.exists(path):
                    os.remove(path)

    def test_camera_shm_client_matches_contextless_feedback_by_subject(self):
        command_path = "/dev/shm/test_py_camera_command_contextless"
        feedback_path = "/dev/shm/test_py_camera_feedback_contextless"
        for path in (command_path, feedback_path):
            if os.path.exists(path):
                os.remove(path)

        init_shm(command_path, 40960)
        init_shm(feedback_path, 40960)
        client = CameraShmClient(command_path, feedback_path, command_capacity=40960, timeout_ms=100)
        producer = ShmProducer(feedback_path, 40960)
        try:
            producer.write(build_feedback_packet(
                DEVICE_CAMERA,
                COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE,
                FEEDBACK_RESPONSE,
                STATUS_OK,
                request_timestamp_us=0,
            ))
            producer.write(build_feedback_packet(
                DEVICE_CAMERA,
                COMMAND_CAMERA_LENS_QUERY_ZOOM,
                FEEDBACK_RESPONSE,
                STATUS_OK,
                request_timestamp_us=0,
            ))

            feedback = client.wait_feedback(123456, COMMAND_CAMERA_LENS_QUERY_ZOOM, timeout_ms=100)
            self.assertEqual(feedback.request_timestamp_us, 0)
            self.assertEqual(feedback.subject_type, COMMAND_CAMERA_LENS_QUERY_ZOOM)
            self.assertEqual(feedback.status, STATUS_OK)
        finally:
            producer.close()
            client.close()
            for path in (command_path, feedback_path):
                if os.path.exists(path):
                    os.remove(path)

    def test_camera_shm_client_reads_parsed_feedback(self):
        command_path = "/dev/shm/test_py_camera_command_read_parsed"
        feedback_path = "/dev/shm/test_py_camera_feedback_read_parsed"
        for path in (command_path, feedback_path):
            if os.path.exists(path):
                os.remove(path)

        init_shm(command_path, 40960)
        init_shm(feedback_path, 40960)
        client = CameraShmClient(command_path, feedback_path, command_capacity=40960, timeout_ms=100)
        producer = ShmProducer(feedback_path, 40960)
        try:
            producer.write(build_feedback_packet(
                DEVICE_CAMERA,
                COMMAND_CAMERA_LENS_QUERY_ZOOM,
                FEEDBACK_RESPONSE,
                STATUS_OK,
                request_timestamp_us=0,
                data_format=DATA_CAMERA_LENS_POSITION,
                data=b"\x5D\x12\x34",
            ))

            parsed = client.read_parsed_feedback(timeout_ms=100)
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed["subjectKey"], "lens_query_zoom")
            self.assertEqual(parsed["dataFormatName"], "CAMERA_LENS_POSITION")
            self.assertEqual(parsed["data"]["lensPositionType"], "zoom")
            self.assertEqual(parsed["data"]["position"], 0x1234)
        finally:
            producer.close()
            client.close()
            for path in (command_path, feedback_path):
                if os.path.exists(path):
                    os.remove(path)

    def test_camera_shm_client_feedback_timeout(self):
        command_path = "/dev/shm/test_py_camera_command_timeout"
        feedback_path = "/dev/shm/test_py_camera_feedback_timeout"
        for path in (command_path, feedback_path):
            if os.path.exists(path):
                os.remove(path)

        init_shm(command_path, 40960)
        client = CameraShmClient(command_path, feedback_path, command_capacity=40960, timeout_ms=5)
        try:
            with self.assertRaises(TimeoutError):
                client.wait_feedback(123456, COMMAND_CAMERA_LENS_STOP, timeout_ms=5)
        finally:
            client.close()
            for path in (command_path, feedback_path):
                if os.path.exists(path):
                    os.remove(path)

    def test_feedback_payload_round_trip_camera_and_turntable(self):
        camera_payload = build_feedback_payload(
            DEVICE_CAMERA,
            COMMAND_CAMERA_LENS_STOP,
            FEEDBACK_ACK,
            STATUS_OK,
            request_timestamp_us=111,
            data_format=DATA_NONE,
        )
        camera_feedback = parse_feedback_payload(camera_payload)
        self.assertEqual(
            camera_feedback,
            DeviceFeedback(
                version=1,
                device_type=DEVICE_CAMERA,
                subject_type=COMMAND_CAMERA_LENS_STOP,
                feedback_kind=FEEDBACK_ACK,
                status=STATUS_OK,
                request_timestamp_us=111,
                data_format=DATA_NONE,
                data=b"",
            ),
        )

        turntable_payload = build_feedback_payload(
            DEVICE_TURNTABLE,
            COMMAND_TURNTABLE_POSITION,
            FEEDBACK_RESPONSE,
            STATUS_INVALID_PARAM,
            request_timestamp_us=222,
            data_format=DATA_TURNTABLE_STATE,
            data=b"\xAA\x55",
        )
        turntable_feedback = parse_feedback_payload(turntable_payload)
        self.assertEqual(turntable_feedback.device_type, DEVICE_TURNTABLE)
        self.assertEqual(turntable_feedback.subject_type, COMMAND_TURNTABLE_POSITION)
        self.assertEqual(turntable_feedback.data, b"\xAA\x55")

    def test_parse_camera_feedback_business_data(self):
        laser_measure = parse_camera_feedback_data(
            DATA_CAMERA_LASER_MEASURE,
            bytes.fromhex("01 A8 00 00 04 D2 00 00 00 64 00 00 00 00"),
        )
        self.assertEqual(laser_measure["laserCmd"], "0x01")
        self.assertEqual(laser_measure["measureStatus"], 0xA8)
        self.assertEqual(laser_measure["distanceA"], 1234)
        self.assertEqual(laser_measure["distanceB"], 100)

        lens_position = parse_camera_feedback_data(DATA_CAMERA_LENS_POSITION, b"\x5D\x12\x34")
        self.assertEqual(lens_position["lensPositionType"], "zoom")
        self.assertEqual(lens_position["position"], 0x1234)

        parsed = parse_camera_feedback(DeviceFeedback(
            version=1,
            device_type=DEVICE_CAMERA,
            subject_type=COMMAND_CAMERA_LENS_QUERY_ZOOM,
            feedback_kind=FEEDBACK_RESPONSE,
            status=STATUS_OK,
            request_timestamp_us=0,
            data_format=DATA_CAMERA_LENS_POSITION,
            data=b"\x5D\x12\x34",
        ))
        self.assertEqual(parsed["subjectKey"], "lens_query_zoom")
        self.assertEqual(parsed["statusName"], "OK")
        self.assertEqual(parsed["dataFormatName"], "CAMERA_LENS_POSITION")
        self.assertEqual(parsed["data"]["position"], 0x1234)

    def test_control_and_feedback_packet_types_are_unsigned(self):
        control_packet = build_control_packet(
            DEVICE_CAMERA,
            COMMAND_CAMERA_LENS_STOP,
            timestamp_us=1000,
        )
        parsed_control = parse_packet(control_packet)
        self.assertEqual(parsed_control.type, TYPE_CONTROL_COMMAND)
        self.assertEqual(parsed_control.timestamp_us, 1000)
        self.assertEqual(parsed_control.payload, bytes.fromhex("00 02 02 11"))

        feedback_packet = build_feedback_packet(
            DEVICE_CAMERA,
            COMMAND_CAMERA_LENS_STOP,
            FEEDBACK_ACK,
            STATUS_OK,
            request_timestamp_us=1000,
            timestamp_us=1001,
        )
        parsed_feedback = parse_packet(feedback_packet)
        self.assertEqual(parsed_feedback.type, TYPE_DEVICE_FEEDBACK)
        self.assertEqual(parsed_feedback.timestamp_us, 1001)
        self.assertEqual(parse_feedback_payload(parsed_feedback.payload).request_timestamp_us, 1000)

class TestMidwareShm(unittest.TestCase):
    def setUp(self):
        # Clean previous
        if os.path.exists(SHM_PATH):
            os.remove(SHM_PATH)

    def tearDown(self):
        if os.path.exists(SHM_PATH):
            os.remove(SHM_PATH)

    def test_producer_requires_existing_initialized_shm(self):
        with self.assertRaises(RuntimeError):
            ShmProducer(SHM_PATH, CAPACITY)

    def test_basic_rw(self):
        print("\n[PYTHON TEST] Init test SHM and attach writer...")
        init_shm(SHM_PATH, CAPACITY)
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
        init_shm(SHM_PATH, CAPACITY)
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
        init_shm(SHM_PATH, CAPACITY)
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

class TestMidwareNet(unittest.TestCase):
    def test_udp_raw_and_packet(self):
        consumer = UdpConsumer(bind_host="127.0.0.1", port=0, timeout_ms=1000)
        producer = UdpProducer("127.0.0.1", consumer.local_port, bind_host="127.0.0.1", timeout_ms=1000)
        try:
            raw = b"udp raw payload"
            self.assertEqual(producer.write(raw), len(raw))
            self.assertEqual(consumer.read(), raw)

            payload = b"udp packet payload"
            self.assertEqual(producer.write_packet(payload, type_id=1, timestamp_us=123456), 13 + len(payload))
            pkt = consumer.read_packet()
            self.assertIsNotNone(pkt)
            self.assertEqual(pkt.type, 1)
            self.assertEqual(pkt.timestamp_us, 123456)
            self.assertEqual(pkt.payload, payload)
            print("\n[PYTHON TEST] UDP network rw verified.")
        finally:
            producer.close()
            consumer.close()

    def test_tcp_packet_bytes_and_reconnect(self):
        consumer = TcpConsumer(bind_host="127.0.0.1", port=0, timeout_ms=1000)
        producer = TcpProducer("127.0.0.1", consumer.local_port, timeout_ms=1000)
        producer2 = None
        try:
            raw = serialize_packet(1, 111, b"tcp raw packet")
            self.assertEqual(producer.write_packet_bytes(raw), len(raw))
            self.assertEqual(consumer.read_packet_bytes(), raw)

            payload = b"tcp parsed packet"
            self.assertEqual(producer.write_packet(payload, type_id=2, timestamp_us=222), 13 + len(payload))
            pkt = consumer.read_packet()
            self.assertIsNotNone(pkt)
            self.assertEqual(pkt.type, 2)
            self.assertEqual(pkt.timestamp_us, 222)
            self.assertEqual(pkt.payload, payload)

            producer.close()
            producer2 = TcpProducer("127.0.0.1", consumer.local_port, timeout_ms=1000)
            payload2 = b"tcp after reconnect"
            self.assertEqual(producer2.write_packet(payload2, type_id=3, timestamp_us=333), 13 + len(payload2))
            pkt2 = consumer.read_packet()
            self.assertIsNotNone(pkt2)
            self.assertEqual(pkt2.type, 3)
            self.assertEqual(pkt2.timestamp_us, 333)
            self.assertEqual(pkt2.payload, payload2)
            print("\n[PYTHON TEST] TCP network rw and reconnect verified.")
        finally:
            producer.close()
            if producer2 is not None:
                producer2.close()
            consumer.close()

if __name__ == '__main__':
    unittest.main()
