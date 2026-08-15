#include "midware_control.h"
#include "midware_net.h"

#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>

uint16_t midware_read_u16_be(const uint8_t* ptr) {
    return (uint16_t)(((uint16_t)ptr[0] << 8) | (uint16_t)ptr[1]);
}

uint32_t midware_read_u32_be(const uint8_t* ptr) {
    return ((uint32_t)ptr[0] << 24) |
           ((uint32_t)ptr[1] << 16) |
           ((uint32_t)ptr[2] << 8) |
           (uint32_t)ptr[3];
}

uint64_t midware_read_u64_be(const uint8_t* ptr) {
    return ((uint64_t)ptr[0] << 56) | ((uint64_t)ptr[1] << 48) |
           ((uint64_t)ptr[2] << 40) | ((uint64_t)ptr[3] << 32) |
           ((uint64_t)ptr[4] << 24) | ((uint64_t)ptr[5] << 16) |
           ((uint64_t)ptr[6] << 8) | (uint64_t)ptr[7];
}

void midware_write_u16_be(uint8_t* ptr, uint16_t value) {
    ptr[0] = (uint8_t)((value >> 8) & 0xFF);
    ptr[1] = (uint8_t)(value & 0xFF);
}

void midware_write_u32_be(uint8_t* ptr, uint32_t value) {
    ptr[0] = (uint8_t)((value >> 24) & 0xFF);
    ptr[1] = (uint8_t)((value >> 16) & 0xFF);
    ptr[2] = (uint8_t)((value >> 8) & 0xFF);
    ptr[3] = (uint8_t)(value & 0xFF);
}

void midware_write_u64_be(uint8_t* ptr, uint64_t value) {
    ptr[0] = (uint8_t)((value >> 56) & 0xFF);
    ptr[1] = (uint8_t)((value >> 48) & 0xFF);
    ptr[2] = (uint8_t)((value >> 40) & 0xFF);
    ptr[3] = (uint8_t)((value >> 32) & 0xFF);
    ptr[4] = (uint8_t)((value >> 24) & 0xFF);
    ptr[5] = (uint8_t)((value >> 16) & 0xFF);
    ptr[6] = (uint8_t)((value >> 8) & 0xFF);
    ptr[7] = (uint8_t)(value & 0xFF);
}

int32_t midware_control_build_payload(void* buffer,
                                      int32_t buffer_len,
                                      uint16_t device_type,
                                      uint16_t command_type,
                                      const void* params,
                                      uint32_t params_len) {
    uint32_t needed = MIDWARE_CONTROL_MIN_PAYLOAD_LEN + params_len;
    if (!buffer || buffer_len < 0 || needed > (uint32_t)buffer_len || (!params && params_len > 0)) {
        errno = EINVAL;
        return MIDWARE_CONTROL_ERR_BUFFER_TOO_SMALL;
    }

    uint8_t* out = (uint8_t*)buffer;
    midware_write_u16_be(out, device_type);
    midware_write_u16_be(out + 2, command_type);
    if (params_len > 0) {
        memcpy(out + MIDWARE_CONTROL_MIN_PAYLOAD_LEN, params, params_len);
    }
    return (int32_t)needed;
}

int midware_control_parse_payload(const void* payload,
                                  uint32_t payload_len,
                                  uint64_t request_timestamp_us,
                                  midware_control_command_t* out_command) {
    if (!payload || !out_command || payload_len < MIDWARE_CONTROL_MIN_PAYLOAD_LEN) {
        return MIDWARE_CONTROL_ERR_BAD_PAYLOAD;
    }

    const uint8_t* raw = (const uint8_t*)payload;
    out_command->request_timestamp_us = request_timestamp_us;
    out_command->device_type = midware_read_u16_be(raw);
    out_command->command_type = midware_read_u16_be(raw + 2);
    out_command->params = raw + MIDWARE_CONTROL_MIN_PAYLOAD_LEN;
    out_command->params_len = payload_len - MIDWARE_CONTROL_MIN_PAYLOAD_LEN;
    return 0;
}

int32_t midware_control_read(midware_tcp_conn_t* conn,
                             void* packet_buf,
                             int32_t packet_buf_len,
                             uint32_t max_frame_length,
                             midware_control_command_t* out_command) {
    midware_packet_header_t header;
    const void* payload = NULL;
    int32_t len = midware_tcp_read_packet(conn,
                                          packet_buf,
                                          packet_buf_len,
                                          max_frame_length,
                                          &header,
                                          &payload);
    if (len <= 0) {
        return len;
    }
    if (header.type != MIDWARE_TYPE_CONTROL_COMMAND) {
        return MIDWARE_CONTROL_ERR_WRONG_TYPE;
    }
    int rc = midware_control_parse_payload(payload,
                                           header.payload_len,
                                           header.timestamp_us,
                                           out_command);
    return rc == 0 ? len : rc;
}

int32_t midware_feedback_build_payload(void* buffer,
                                       int32_t buffer_len,
                                       uint16_t device_type,
                                       uint16_t subject_type,
                                       uint8_t feedback_kind,
                                       uint16_t status,
                                       uint64_t request_timestamp_us,
                                       uint16_t data_format,
                                       const void* data,
                                       uint32_t data_len) {
    uint32_t needed = MIDWARE_FEEDBACK_HEADER_LEN + data_len;
    if (!buffer || buffer_len < 0 || needed > (uint32_t)buffer_len || (!data && data_len > 0)) {
        errno = EINVAL;
        return MIDWARE_CONTROL_ERR_BUFFER_TOO_SMALL;
    }

    uint8_t* out = (uint8_t*)buffer;
    out[0] = MIDWARE_FEEDBACK_VERSION;
    midware_write_u16_be(out + 1, device_type);
    midware_write_u16_be(out + 3, subject_type);
    out[5] = feedback_kind;
    midware_write_u16_be(out + 6, status);
    midware_write_u64_be(out + 8, request_timestamp_us);
    midware_write_u16_be(out + 16, data_format);
    if (data_len > 0) {
        memcpy(out + MIDWARE_FEEDBACK_HEADER_LEN, data, data_len);
    }
    return (int32_t)needed;
}

int midware_feedback_parse_payload(const void* payload,
                                   uint32_t payload_len,
                                   midware_device_feedback_t* out_feedback) {
    if (!payload || !out_feedback || payload_len < MIDWARE_FEEDBACK_HEADER_LEN) {
        return MIDWARE_CONTROL_ERR_BAD_PAYLOAD;
    }

    const uint8_t* raw = (const uint8_t*)payload;
    if (raw[0] != MIDWARE_FEEDBACK_VERSION) {
        return MIDWARE_CONTROL_ERR_BAD_PAYLOAD;
    }

    out_feedback->version = raw[0];
    out_feedback->device_type = midware_read_u16_be(raw + 1);
    out_feedback->subject_type = midware_read_u16_be(raw + 3);
    out_feedback->feedback_kind = raw[5];
    out_feedback->status = midware_read_u16_be(raw + 6);
    out_feedback->request_timestamp_us = midware_read_u64_be(raw + 8);
    out_feedback->data_format = midware_read_u16_be(raw + 16);
    out_feedback->data = raw + MIDWARE_FEEDBACK_HEADER_LEN;
    out_feedback->data_len = payload_len - MIDWARE_FEEDBACK_HEADER_LEN;
    return 0;
}

int32_t midware_feedback_send(midware_tcp_conn_t* conn,
                              uint16_t device_type,
                              uint16_t subject_type,
                              uint8_t feedback_kind,
                              uint16_t status,
                              uint64_t request_timestamp_us,
                              uint16_t data_format,
                              const void* data,
                              uint32_t data_len) {
    uint32_t payload_len = MIDWARE_FEEDBACK_HEADER_LEN + data_len;
    if (payload_len > INT_MAX) {
        errno = EINVAL;
        return MIDWARE_CONTROL_ERR_BUFFER_TOO_SMALL;
    }
    uint8_t* payload = (uint8_t*)malloc(payload_len);
    if (!payload) {
        return MIDWARE_NET_ERR_SOCKET;
    }

    int32_t built = midware_feedback_build_payload(payload,
                                                   (int32_t)payload_len,
                                                   device_type,
                                                   subject_type,
                                                   feedback_kind,
                                                   status,
                                                   request_timestamp_us,
                                                   data_format,
                                                   data,
                                                   data_len);
    if (built < 0) {
        free(payload);
        return built;
    }

    int32_t sent = midware_tcp_send_packet(conn,
                                           MIDWARE_TYPE_DEVICE_FEEDBACK,
                                           request_timestamp_us,
                                           payload,
                                           (uint32_t)built);
    free(payload);
    return sent;
}
