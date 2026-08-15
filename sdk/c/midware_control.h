#ifndef MIDWARE_CONTROL_H
#define MIDWARE_CONTROL_H

#include <stdint.h>

#include "midware_packet.h"
#include "midware_generated_commands.h"

#ifdef __cplusplus
extern "C" {
#endif

#define MIDWARE_CONTROL_MIN_PAYLOAD_LEN 4
#define MIDWARE_FEEDBACK_VERSION 1
#define MIDWARE_FEEDBACK_HEADER_LEN 18

#define MIDWARE_FEEDBACK_ACK 1
#define MIDWARE_FEEDBACK_RESPONSE 2
#define MIDWARE_FEEDBACK_EVENT 3
#define MIDWARE_FEEDBACK_ERROR 4

#define MIDWARE_STATUS_OK 0
#define MIDWARE_STATUS_UNSUPPORTED_DEVICE 1
#define MIDWARE_STATUS_UNSUPPORTED_COMMAND 2
#define MIDWARE_STATUS_INVALID_PARAM 3
#define MIDWARE_STATUS_HARDWARE_WRITE_FAILED 4
#define MIDWARE_STATUS_DEVICE_TIMEOUT 5
#define MIDWARE_STATUS_CHECKSUM_ERROR 6
#define MIDWARE_STATUS_DEVICE_ERROR 7

#define MIDWARE_DATA_NONE 0x0000
#define MIDWARE_DATA_RAW_DEVICE_FRAME 0x0001
#define MIDWARE_DATA_TEXT 0x0002
#define MIDWARE_DATA_TURNTABLE_STATE 0x0101
#define MIDWARE_DATA_CAMERA_LASER_MEASURE 0x0201
#define MIDWARE_DATA_CAMERA_LENS_POSITION 0x0202
#define MIDWARE_DATA_CAMERA_SELF_TEST 0x0203
#define MIDWARE_DATA_CAMERA_IDENTITY 0x0204
#define MIDWARE_DATA_CAMERA_LASER_RESPONSE 0x0205

#define MIDWARE_CONTROL_ERR_INVALID_PACKET (-20)
#define MIDWARE_CONTROL_ERR_WRONG_TYPE (-21)
#define MIDWARE_CONTROL_ERR_BAD_PAYLOAD (-22)
#define MIDWARE_CONTROL_ERR_BUFFER_TOO_SMALL (-23)

typedef struct midware_tcp_conn midware_tcp_conn_t;

typedef struct {
    uint64_t request_timestamp_us;
    uint16_t device_type;
    uint16_t command_type;
    const uint8_t* params;
    uint32_t params_len;
} midware_control_command_t;

typedef struct {
    uint8_t version;
    uint16_t device_type;
    uint16_t subject_type;
    uint8_t feedback_kind;
    uint16_t status;
    uint64_t request_timestamp_us;
    uint16_t data_format;
    const uint8_t* data;
    uint32_t data_len;
} midware_device_feedback_t;

uint16_t midware_read_u16_be(const uint8_t* ptr);
uint32_t midware_read_u32_be(const uint8_t* ptr);
uint64_t midware_read_u64_be(const uint8_t* ptr);
void midware_write_u16_be(uint8_t* ptr, uint16_t value);
void midware_write_u32_be(uint8_t* ptr, uint32_t value);
void midware_write_u64_be(uint8_t* ptr, uint64_t value);

int32_t midware_control_build_payload(void* buffer,
                                      int32_t buffer_len,
                                      uint16_t device_type,
                                      uint16_t command_type,
                                      const void* params,
                                      uint32_t params_len);

int midware_control_parse_payload(const void* payload,
                                  uint32_t payload_len,
                                  uint64_t request_timestamp_us,
                                  midware_control_command_t* out_command);

int32_t midware_control_read(midware_tcp_conn_t* conn,
                             void* packet_buf,
                             int32_t packet_buf_len,
                             uint32_t max_frame_length,
                             midware_control_command_t* out_command);

int32_t midware_feedback_build_payload(void* buffer,
                                       int32_t buffer_len,
                                       uint16_t device_type,
                                       uint16_t subject_type,
                                       uint8_t feedback_kind,
                                       uint16_t status,
                                       uint64_t request_timestamp_us,
                                       uint16_t data_format,
                                       const void* data,
                                       uint32_t data_len);

int midware_feedback_parse_payload(const void* payload,
                                   uint32_t payload_len,
                                   midware_device_feedback_t* out_feedback);

int32_t midware_feedback_send(midware_tcp_conn_t* conn,
                              uint16_t device_type,
                              uint16_t subject_type,
                              uint8_t feedback_kind,
                              uint16_t status,
                              uint64_t request_timestamp_us,
                              uint16_t data_format,
                              const void* data,
                              uint32_t data_len);

#ifdef __cplusplus
}
#endif

#endif
