#include "midware_camera.h"

#include <string.h>

static uint8_t laser_checksum(const uint8_t inner[5]) {
    return inner[0] ^ inner[1] ^ inner[2] ^ inner[3] ^ inner[4];
}

static uint8_t lens_checksum(uint8_t address,
                             uint8_t command1,
                             uint8_t command2,
                             uint8_t data1,
                             uint8_t data2) {
    return (uint8_t)(address + command1 + command2 + data1 + data2);
}

static uint16_t read_u16_be_local(const uint8_t* ptr) {
    return (uint16_t)(((uint16_t)ptr[0] << 8) | (uint16_t)ptr[1]);
}

static int expect_no_params(const midware_control_command_t* command) {
    return command->params_len == 0 ? 0 : MIDWARE_CAMERA_ERR_INVALID_PARAMS;
}

static int read_u8_param(const midware_control_command_t* command,
                         uint8_t min_value,
                         uint8_t max_value,
                         uint8_t* out_value) {
    if (command->params_len != 1 || !command->params) {
        return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
    }
    uint8_t value = command->params[0];
    if (value < min_value || value > max_value) {
        return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
    }
    *out_value = value;
    return 0;
}

static int read_u16_param(const midware_control_command_t* command, uint16_t* out_value) {
    if (command->params_len != 2 || !command->params) {
        return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
    }
    *out_value = read_u16_be_local(command->params);
    return 0;
}

static int build_laser_frame(uint8_t cmd,
                             uint16_t data,
                             uint8_t* out_frame,
                             uint32_t out_capacity,
                             uint32_t* out_len) {
    if (!out_frame || !out_len || out_capacity < 10) {
        return MIDWARE_CAMERA_ERR_BUFFER_TOO_SMALL;
    }
    uint8_t inner[5] = {
        0x55,
        cmd,
        0x02,
        (uint8_t)((data >> 8) & 0xFF),
        (uint8_t)(data & 0xFF),
    };
    out_frame[0] = 0xFF;
    out_frame[1] = 0x01;
    out_frame[2] = 0x05;
    out_frame[3] = 0x06;
    memcpy(out_frame + 4, inner, sizeof(inner));
    out_frame[9] = laser_checksum(inner);
    *out_len = 10;
    return 0;
}

static int build_lens_frame(uint8_t command1,
                            uint8_t command2,
                            uint8_t data1,
                            uint8_t data2,
                            uint8_t* out_frame,
                            uint32_t out_capacity,
                            uint32_t* out_len) {
    if (!out_frame || !out_len || out_capacity < 11) {
        return MIDWARE_CAMERA_ERR_BUFFER_TOO_SMALL;
    }
    out_frame[0] = 0xFF;
    out_frame[1] = 0x01;
    out_frame[2] = 0x04;
    out_frame[3] = 0x07;
    out_frame[4] = 0xFF;
    out_frame[5] = 0x01;
    out_frame[6] = command1;
    out_frame[7] = command2;
    out_frame[8] = data1;
    out_frame[9] = data2;
    out_frame[10] = lens_checksum(out_frame[5], command1, command2, data1, data2);
    *out_len = 11;
    return 0;
}

int midware_camera_command_to_frame(const midware_control_command_t* command,
                                    uint8_t* out_frame,
                                    uint32_t out_capacity,
                                    uint32_t* out_len) {
    if (out_len) {
        *out_len = 0;
    }
    if (!command || !out_frame || !out_len) {
        return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
    }
    if (command->device_type != MIDWARE_DEVICE_CAMERA) {
        return MIDWARE_CAMERA_ERR_UNSUPPORTED_COMMAND;
    }

    uint8_t value_u8 = 0;
    uint16_t value_u16 = 0;

    switch (command->command_type) {
        case MIDWARE_COMMAND_CAMERA_LASER_STANDBY:
            if (expect_no_params(command) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_laser_frame(0x00, 0x0000, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LASER_SINGLE_MEASURE:
            if (expect_no_params(command) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_laser_frame(0x01, 0x0000, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LASER_CONTINUOUS_MEASURE:
            if (read_u16_param(command, &value_u16) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_laser_frame(0x02, value_u16, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LASER_SELF_TEST:
            if (expect_no_params(command) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_laser_frame(0x03, 0x0000, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LASER_SET_NEAREST_DISTANCE:
            if (read_u16_param(command, &value_u16) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_laser_frame(0x04, value_u16, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LASER_QUERY_SHOT_COUNT:
            if (expect_no_params(command) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_laser_frame(0x06, 0x0000, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LASER_SET_FARTHEST_DISTANCE:
            if (read_u16_param(command, &value_u16) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_laser_frame(0x0B, value_u16, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LASER_APD_POWER_ON:
            if (expect_no_params(command) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_laser_frame(0x11, 0x0000, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LASER_APD_POWER_OFF:
            if (expect_no_params(command) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_laser_frame(0x12, 0x0000, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LASER_SET_WORK_TIMEOUT:
            if (read_u16_param(command, &value_u16) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_laser_frame(0x20, value_u16, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LASER_QUERY_ID:
            if (expect_no_params(command) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_laser_frame(0xEB, 0x0000, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_ZOOM_IN:
            if (read_u8_param(command, 1, 63, &value_u8) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x00, 0x20, 0x00, value_u8, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_ZOOM_OUT:
            if (read_u8_param(command, 1, 63, &value_u8) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x00, 0x40, 0x00, value_u8, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_FOCUS_PLUS:
            if (read_u8_param(command, 1, 63, &value_u8) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x01, 0x00, 0x00, value_u8, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_FOCUS_MINUS:
            if (read_u8_param(command, 1, 63, &value_u8) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x00, 0x80, 0x00, value_u8, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_IRIS_PLUS:
            if (read_u8_param(command, 1, 63, &value_u8) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x02, 0x00, 0x00, value_u8, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_IRIS_MINUS:
            if (read_u8_param(command, 1, 63, &value_u8) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x04, 0x00, 0x00, value_u8, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_RELAY_ON:
            if (read_u8_param(command, 1, 8, &value_u8) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x00, 0x09, 0x00, value_u8, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_RELAY_OFF:
            if (read_u8_param(command, 1, 8, &value_u8) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x00, 0x0B, 0x00, value_u8, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_SET_PRESET:
            if (read_u8_param(command, 1, 255, &value_u8) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x00, 0x03, 0x00, value_u8, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_CALL_PRESET:
            if (read_u8_param(command, 1, 255, &value_u8) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x00, 0x07, 0x00, value_u8, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_QUERY_ZOOM:
            if (expect_no_params(command) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x00, 0x55, 0x00, 0x00, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_QUERY_FOCUS:
            if (expect_no_params(command) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x00, 0x56, 0x00, 0x00, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_QUERY_IRIS:
            if (expect_no_params(command) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x00, 0x57, 0x00, 0x00, out_frame, out_capacity, out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_GOTO_ZOOM:
            if (read_u16_param(command, &value_u16) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x00,
                                    0x4F,
                                    (uint8_t)((value_u16 >> 8) & 0xFF),
                                    (uint8_t)(value_u16 & 0xFF),
                                    out_frame,
                                    out_capacity,
                                    out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_GOTO_FOCUS:
            if (read_u16_param(command, &value_u16) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x00,
                                    0x4E,
                                    (uint8_t)((value_u16 >> 8) & 0xFF),
                                    (uint8_t)(value_u16 & 0xFF),
                                    out_frame,
                                    out_capacity,
                                    out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_GOTO_IRIS:
            if (read_u16_param(command, &value_u16) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x00,
                                    0x81,
                                    (uint8_t)((value_u16 >> 8) & 0xFF),
                                    (uint8_t)(value_u16 & 0xFF),
                                    out_frame,
                                    out_capacity,
                                    out_len);

        case MIDWARE_COMMAND_CAMERA_LENS_STOP:
            if (expect_no_params(command) != 0) {
                return MIDWARE_CAMERA_ERR_INVALID_PARAMS;
            }
            return build_lens_frame(0x00, 0x00, 0x00, 0x00, out_frame, out_capacity, out_len);

        default:
            return MIDWARE_CAMERA_ERR_UNSUPPORTED_COMMAND;
    }
}
