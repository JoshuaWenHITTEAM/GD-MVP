#include "midware_camera.h"
#include "midware_control.h"
#include "midware_packet.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void fail(const char* msg) {
    fprintf(stderr, "FAIL: %s\n", msg);
    exit(1);
}

static void expect_int(const char* msg, int actual, int expected) {
    if (actual != expected) {
        fprintf(stderr, "FAIL: %s: actual=%d expected=%d\n", msg, actual, expected);
        exit(1);
    }
}

static void expect_bytes(const char* msg, const uint8_t* actual, const uint8_t* expected, size_t len) {
    if (memcmp(actual, expected, len) != 0) {
        fprintf(stderr, "FAIL: %s\nactual:  ", msg);
        for (size_t i = 0; i < len; i++) fprintf(stderr, "%02X ", actual[i]);
        fprintf(stderr, "\nexpected:");
        for (size_t i = 0; i < len; i++) fprintf(stderr, "%02X ", expected[i]);
        fprintf(stderr, "\n");
        exit(1);
    }
}

static void expect_camera_frame(const char* msg,
                                uint16_t command_type,
                                const uint8_t* params,
                                uint32_t params_len,
                                const uint8_t* expected,
                                uint32_t expected_len) {
    midware_control_command_t cmd;
    cmd.request_timestamp_us = 1;
    cmd.device_type = MIDWARE_DEVICE_CAMERA;
    cmd.command_type = command_type;
    cmd.params = params;
    cmd.params_len = params_len;

    uint8_t frame[32];
    uint32_t frame_len = 123;
    expect_int(msg, midware_camera_command_to_frame(&cmd, frame, sizeof(frame), &frame_len), 0);
    expect_int("camera frame len", frame_len, expected_len);
    expect_bytes(msg, frame, expected, expected_len);
}

static void expect_camera_error(const char* msg,
                                midware_control_command_t* cmd,
                                uint8_t* frame,
                                uint32_t frame_capacity,
                                int expected_error) {
    uint32_t frame_len = 123;
    expect_int(msg,
               midware_camera_command_to_frame(cmd, frame, frame_capacity, &frame_len),
               expected_error);
    expect_int("camera error out_len", frame_len, 0);
}

static void test_control_payload(void) {
    uint8_t params[] = {0x03, 0xE8};
    uint8_t payload[16];
    int32_t len = midware_control_build_payload(payload,
                                                sizeof(payload),
                                                MIDWARE_DEVICE_CAMERA,
                                                MIDWARE_COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE,
                                                params,
                                                sizeof(params));
    expect_int("control build len", len, 6);
    const uint8_t expected[] = {0x00, 0x02, 0x01, 0x03, 0x03, 0xE8};
    expect_bytes("control build bytes", payload, expected, sizeof(expected));

    midware_control_command_t cmd;
    expect_int("control parse",
               midware_control_parse_payload(payload, (uint32_t)len, 123456, &cmd),
               0);
    expect_int("control device", cmd.device_type, MIDWARE_DEVICE_CAMERA);
    expect_int("control command", cmd.command_type, MIDWARE_COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE);
    expect_int("control params len", cmd.params_len, 2);
    if (cmd.request_timestamp_us != 123456) {
        fail("control request timestamp");
    }
}

static void test_feedback_payload(void) {
    uint8_t data[] = {0xAA, 0x55};
    uint8_t payload[64];
    int32_t len = midware_feedback_build_payload(payload,
                                                 sizeof(payload),
                                                 MIDWARE_DEVICE_TURNTABLE,
                                                 MIDWARE_COMMAND_TURNTABLE_POSITION,
                                                 MIDWARE_FEEDBACK_RESPONSE,
                                                 MIDWARE_STATUS_OK,
                                                 987654,
                                                 MIDWARE_DATA_TURNTABLE_STATE,
                                                 data,
                                                 sizeof(data));
    expect_int("feedback build len", len, MIDWARE_FEEDBACK_HEADER_LEN + 2);

    midware_device_feedback_t fb;
    expect_int("feedback parse",
               midware_feedback_parse_payload(payload, (uint32_t)len, &fb),
               0);
    expect_int("feedback version", fb.version, MIDWARE_FEEDBACK_VERSION);
    expect_int("feedback device", fb.device_type, MIDWARE_DEVICE_TURNTABLE);
    expect_int("feedback subject", fb.subject_type, MIDWARE_COMMAND_TURNTABLE_POSITION);
    expect_int("feedback kind", fb.feedback_kind, MIDWARE_FEEDBACK_RESPONSE);
    expect_int("feedback status", fb.status, MIDWARE_STATUS_OK);
    if (fb.request_timestamp_us != 987654) {
        fail("feedback request timestamp");
    }
    expect_int("feedback format", fb.data_format, MIDWARE_DATA_TURNTABLE_STATE);
    expect_int("feedback data len", fb.data_len, 2);
    expect_bytes("feedback data", fb.data, data, sizeof(data));
}

static void test_camera_frames(void) {
    const uint8_t period[] = {0x03, 0xE8};
    const uint8_t distance_near[] = {0x00, 0x64};
    const uint8_t distance_far[] = {0x13, 0x88};
    const uint8_t timeout[] = {0x00, 0x1E};
    const uint8_t one[] = {0x01};
    const uint8_t position[] = {0x12, 0x34};

    const uint8_t laser_standby[] = {0xFF, 0x01, 0x05, 0x06, 0x55, 0x00, 0x02, 0x00, 0x00, 0x57};
    expect_camera_frame("laser standby frame", MIDWARE_COMMAND_CAMERA_LASER_STANDBY, NULL, 0, laser_standby, sizeof(laser_standby));
    const uint8_t laser_single[] = {0xFF, 0x01, 0x05, 0x06, 0x55, 0x01, 0x02, 0x00, 0x00, 0x56};
    expect_camera_frame("laser single frame", MIDWARE_COMMAND_CAMERA_LASER_SINGLE_MEASURE, NULL, 0, laser_single, sizeof(laser_single));
    const uint8_t laser_continuous[] = {0xFF, 0x01, 0x05, 0x06, 0x55, 0x02, 0x02, 0x03, 0xE8, 0xBE};
    expect_camera_frame("laser continuous frame", MIDWARE_COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE, period, sizeof(period), laser_continuous, sizeof(laser_continuous));
    const uint8_t laser_self_test[] = {0xFF, 0x01, 0x05, 0x06, 0x55, 0x03, 0x02, 0x00, 0x00, 0x54};
    expect_camera_frame("laser self test frame", MIDWARE_COMMAND_CAMERA_LASER_SELF_TEST, NULL, 0, laser_self_test, sizeof(laser_self_test));
    const uint8_t laser_nearest[] = {0xFF, 0x01, 0x05, 0x06, 0x55, 0x04, 0x02, 0x00, 0x64, 0x37};
    expect_camera_frame("laser nearest frame", MIDWARE_COMMAND_CAMERA_LASER_SET_NEAREST_DISTANCE, distance_near, sizeof(distance_near), laser_nearest, sizeof(laser_nearest));
    const uint8_t laser_shot_count[] = {0xFF, 0x01, 0x05, 0x06, 0x55, 0x06, 0x02, 0x00, 0x00, 0x51};
    expect_camera_frame("laser shot count frame", MIDWARE_COMMAND_CAMERA_LASER_QUERY_SHOT_COUNT, NULL, 0, laser_shot_count, sizeof(laser_shot_count));
    const uint8_t laser_farthest[] = {0xFF, 0x01, 0x05, 0x06, 0x55, 0x0B, 0x02, 0x13, 0x88, 0xC7};
    expect_camera_frame("laser farthest frame", MIDWARE_COMMAND_CAMERA_LASER_SET_FARTHEST_DISTANCE, distance_far, sizeof(distance_far), laser_farthest, sizeof(laser_farthest));
    const uint8_t laser_apd_on[] = {0xFF, 0x01, 0x05, 0x06, 0x55, 0x11, 0x02, 0x00, 0x00, 0x46};
    expect_camera_frame("laser apd on frame", MIDWARE_COMMAND_CAMERA_LASER_APD_POWER_ON, NULL, 0, laser_apd_on, sizeof(laser_apd_on));
    const uint8_t laser_apd_off[] = {0xFF, 0x01, 0x05, 0x06, 0x55, 0x12, 0x02, 0x00, 0x00, 0x45};
    expect_camera_frame("laser apd off frame", MIDWARE_COMMAND_CAMERA_LASER_APD_POWER_OFF, NULL, 0, laser_apd_off, sizeof(laser_apd_off));
    const uint8_t laser_timeout[] = {0xFF, 0x01, 0x05, 0x06, 0x55, 0x20, 0x02, 0x00, 0x1E, 0x69};
    expect_camera_frame("laser timeout frame", MIDWARE_COMMAND_CAMERA_LASER_SET_WORK_TIMEOUT, timeout, sizeof(timeout), laser_timeout, sizeof(laser_timeout));
    const uint8_t laser_id[] = {0xFF, 0x01, 0x05, 0x06, 0x55, 0xEB, 0x02, 0x00, 0x00, 0xBC};
    expect_camera_frame("laser id frame", MIDWARE_COMMAND_CAMERA_LASER_QUERY_ID, NULL, 0, laser_id, sizeof(laser_id));

    const uint8_t lens_zoom_in[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x00, 0x20, 0x00, 0x01, 0x22};
    expect_camera_frame("lens zoom in frame", MIDWARE_COMMAND_CAMERA_LENS_ZOOM_IN, one, sizeof(one), lens_zoom_in, sizeof(lens_zoom_in));
    const uint8_t lens_zoom_out[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x00, 0x40, 0x00, 0x01, 0x42};
    expect_camera_frame("lens zoom out frame", MIDWARE_COMMAND_CAMERA_LENS_ZOOM_OUT, one, sizeof(one), lens_zoom_out, sizeof(lens_zoom_out));
    const uint8_t lens_focus_plus[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x01, 0x00, 0x00, 0x01, 0x03};
    expect_camera_frame("lens focus plus frame", MIDWARE_COMMAND_CAMERA_LENS_FOCUS_PLUS, one, sizeof(one), lens_focus_plus, sizeof(lens_focus_plus));
    const uint8_t lens_focus_minus[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x00, 0x80, 0x00, 0x01, 0x82};
    expect_camera_frame("lens focus minus frame", MIDWARE_COMMAND_CAMERA_LENS_FOCUS_MINUS, one, sizeof(one), lens_focus_minus, sizeof(lens_focus_minus));
    const uint8_t lens_iris_plus[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x02, 0x00, 0x00, 0x01, 0x04};
    expect_camera_frame("lens iris plus frame", MIDWARE_COMMAND_CAMERA_LENS_IRIS_PLUS, one, sizeof(one), lens_iris_plus, sizeof(lens_iris_plus));
    const uint8_t lens_iris_minus[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x04, 0x00, 0x00, 0x01, 0x06};
    expect_camera_frame("lens iris minus frame", MIDWARE_COMMAND_CAMERA_LENS_IRIS_MINUS, one, sizeof(one), lens_iris_minus, sizeof(lens_iris_minus));
    const uint8_t lens_relay_on[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x00, 0x09, 0x00, 0x01, 0x0B};
    expect_camera_frame("lens relay on frame", MIDWARE_COMMAND_CAMERA_LENS_RELAY_ON, one, sizeof(one), lens_relay_on, sizeof(lens_relay_on));
    const uint8_t lens_relay_off[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x00, 0x0B, 0x00, 0x01, 0x0D};
    expect_camera_frame("lens relay off frame", MIDWARE_COMMAND_CAMERA_LENS_RELAY_OFF, one, sizeof(one), lens_relay_off, sizeof(lens_relay_off));
    const uint8_t lens_set_preset[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x00, 0x03, 0x00, 0x01, 0x05};
    expect_camera_frame("lens set preset frame", MIDWARE_COMMAND_CAMERA_LENS_SET_PRESET, one, sizeof(one), lens_set_preset, sizeof(lens_set_preset));
    const uint8_t lens_call_preset[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x00, 0x07, 0x00, 0x01, 0x09};
    expect_camera_frame("lens call preset frame", MIDWARE_COMMAND_CAMERA_LENS_CALL_PRESET, one, sizeof(one), lens_call_preset, sizeof(lens_call_preset));
    const uint8_t lens_query_zoom[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x00, 0x55, 0x00, 0x00, 0x56};
    expect_camera_frame("lens query zoom frame", MIDWARE_COMMAND_CAMERA_LENS_QUERY_ZOOM, NULL, 0, lens_query_zoom, sizeof(lens_query_zoom));
    const uint8_t lens_query_focus[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x00, 0x56, 0x00, 0x00, 0x57};
    expect_camera_frame("lens query focus frame", MIDWARE_COMMAND_CAMERA_LENS_QUERY_FOCUS, NULL, 0, lens_query_focus, sizeof(lens_query_focus));
    const uint8_t lens_query_iris[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x00, 0x57, 0x00, 0x00, 0x58};
    expect_camera_frame("lens query iris frame", MIDWARE_COMMAND_CAMERA_LENS_QUERY_IRIS, NULL, 0, lens_query_iris, sizeof(lens_query_iris));
    const uint8_t lens_goto_zoom[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x00, 0x4F, 0x12, 0x34, 0x96};
    expect_camera_frame("lens goto zoom frame", MIDWARE_COMMAND_CAMERA_LENS_GOTO_ZOOM, position, sizeof(position), lens_goto_zoom, sizeof(lens_goto_zoom));
    const uint8_t lens_goto_focus[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x00, 0x4E, 0x12, 0x34, 0x95};
    expect_camera_frame("lens goto focus frame", MIDWARE_COMMAND_CAMERA_LENS_GOTO_FOCUS, position, sizeof(position), lens_goto_focus, sizeof(lens_goto_focus));
    const uint8_t lens_goto_iris[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x00, 0x81, 0x12, 0x34, 0xC8};
    expect_camera_frame("lens goto iris frame", MIDWARE_COMMAND_CAMERA_LENS_GOTO_IRIS, position, sizeof(position), lens_goto_iris, sizeof(lens_goto_iris));
    const uint8_t lens_stop[] = {0xFF, 0x01, 0x04, 0x07, 0xFF, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01};
    expect_camera_frame("lens stop frame", MIDWARE_COMMAND_CAMERA_LENS_STOP, NULL, 0, lens_stop, sizeof(lens_stop));
}

static void test_camera_invalid_inputs(void) {
    uint8_t frame[32];
    uint8_t speed_zero[] = {0x00};
    uint8_t speed_too_high[] = {0x40};
    uint8_t relay_zero[] = {0x00};
    uint8_t relay_too_high[] = {0x09};
    uint8_t preset_zero[] = {0x00};
    uint8_t wrong_len[] = {0x00, 0x01, 0x02};
    uint8_t valid_period[] = {0x03, 0xE8};

    midware_control_command_t cmd;
    cmd.request_timestamp_us = 1;
    cmd.device_type = MIDWARE_DEVICE_CAMERA;
    cmd.command_type = MIDWARE_COMMAND_CAMERA_LENS_ZOOM_IN;
    cmd.params = speed_zero;
    cmd.params_len = sizeof(speed_zero);
    expect_camera_error("lens speed zero", &cmd, frame, sizeof(frame), MIDWARE_CAMERA_ERR_INVALID_PARAMS);
    cmd.params = speed_too_high;
    cmd.params_len = sizeof(speed_too_high);
    expect_camera_error("lens speed too high", &cmd, frame, sizeof(frame), MIDWARE_CAMERA_ERR_INVALID_PARAMS);

    cmd.command_type = MIDWARE_COMMAND_CAMERA_LENS_RELAY_ON;
    cmd.params = relay_zero;
    cmd.params_len = sizeof(relay_zero);
    expect_camera_error("lens relay zero", &cmd, frame, sizeof(frame), MIDWARE_CAMERA_ERR_INVALID_PARAMS);
    cmd.params = relay_too_high;
    cmd.params_len = sizeof(relay_too_high);
    expect_camera_error("lens relay too high", &cmd, frame, sizeof(frame), MIDWARE_CAMERA_ERR_INVALID_PARAMS);

    cmd.command_type = MIDWARE_COMMAND_CAMERA_LENS_SET_PRESET;
    cmd.params = preset_zero;
    cmd.params_len = sizeof(preset_zero);
    expect_camera_error("lens preset zero", &cmd, frame, sizeof(frame), MIDWARE_CAMERA_ERR_INVALID_PARAMS);

    cmd.command_type = MIDWARE_COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE;
    cmd.params = wrong_len;
    cmd.params_len = sizeof(wrong_len);
    expect_camera_error("laser wrong param length", &cmd, frame, sizeof(frame), MIDWARE_CAMERA_ERR_INVALID_PARAMS);

    cmd.command_type = MIDWARE_COMMAND_CAMERA_LENS_STOP;
    cmd.params = speed_zero;
    cmd.params_len = sizeof(speed_zero);
    expect_camera_error("lens stop wrong param length", &cmd, frame, sizeof(frame), MIDWARE_CAMERA_ERR_INVALID_PARAMS);

    cmd.command_type = 0xFFFF;
    cmd.params = NULL;
    cmd.params_len = 0;
    expect_camera_error("unknown camera command", &cmd, frame, sizeof(frame), MIDWARE_CAMERA_ERR_UNSUPPORTED_COMMAND);

    cmd.device_type = MIDWARE_DEVICE_TURNTABLE;
    cmd.command_type = MIDWARE_COMMAND_TURNTABLE_POSITION;
    expect_camera_error("non-camera command", &cmd, frame, sizeof(frame), MIDWARE_CAMERA_ERR_UNSUPPORTED_COMMAND);

    cmd.device_type = MIDWARE_DEVICE_CAMERA;
    cmd.command_type = MIDWARE_COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE;
    cmd.params = valid_period;
    cmd.params_len = sizeof(valid_period);
    expect_camera_error("too-small laser output buffer", &cmd, frame, 4, MIDWARE_CAMERA_ERR_BUFFER_TOO_SMALL);

    cmd.command_type = MIDWARE_COMMAND_CAMERA_LENS_STOP;
    cmd.params = NULL;
    cmd.params_len = 0;
    expect_camera_error("too-small lens output buffer", &cmd, frame, 10, MIDWARE_CAMERA_ERR_BUFFER_TOO_SMALL);
}

int main(void) {
    test_control_payload();
    test_feedback_payload();
    test_camera_frames();
    test_camera_invalid_inputs();
    printf("Control/feedback SDK test passed\n");
    return 0;
}
