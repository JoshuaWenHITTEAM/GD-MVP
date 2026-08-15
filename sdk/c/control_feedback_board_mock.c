#include "midware_camera.h"
#include "midware_control.h"
#include "midware_net.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static int parse_port(const char* text) {
    char* end = NULL;
    long value = strtol(text, &end, 10);
    if (!text[0] || (end && *end) || value <= 0 || value > 65535) {
        return -1;
    }
    return (int)value;
}

static int parse_count(const char* text) {
    char* end = NULL;
    long value = strtol(text, &end, 10);
    if (!text[0] || (end && *end) || value <= 0 || value > 10000) {
        return -1;
    }
    return (int)value;
}

int main(int argc, char** argv) {
    if (argc != 5 && argc != 6) {
        fprintf(stderr,
                "usage: %s <command_host> <command_port> <feedback_host> <feedback_port> [expected_count]\n",
                argv[0]);
        return 2;
    }

    int command_port = parse_port(argv[2]);
    int feedback_port = parse_port(argv[4]);
    int expected_count = argc == 6 ? parse_count(argv[5]) : 1;
    if (command_port < 0 || feedback_port < 0 || expected_count < 0) {
        fprintf(stderr, "invalid port or expected_count\n");
        return 2;
    }

    midware_tcp_conn_t* command_conn = midware_tcp_connect(argv[1], (uint16_t)command_port, 3000);
    if (!command_conn) {
        perror("connect command endpoint");
        return 1;
    }

    midware_tcp_conn_t* feedback_conn = midware_tcp_connect(argv[3], (uint16_t)feedback_port, 3000);
    if (!feedback_conn) {
        perror("connect feedback endpoint");
        midware_tcp_conn_close(command_conn);
        return 1;
    }

    printf("BOARD_MOCK_READY\n");
    fflush(stdout);

    uint8_t packet_buf[4096];
    uint8_t frame[64];
    int ok = 1;

    for (int i = 0; i < expected_count; i++) {
        midware_control_command_t command;
        int32_t read_len = midware_control_read(command_conn,
                                                packet_buf,
                                                sizeof(packet_buf),
                                                MIDWARE_NET_DEFAULT_MAX_FRAME_LENGTH,
                                                &command);
        if (read_len <= 0) {
            fprintf(stderr, "read control failed at index %d: %d\n", i, read_len);
            ok = 0;
            break;
        }

        uint32_t frame_len = 0;
        int codec_rc = midware_camera_command_to_frame(&command, frame, sizeof(frame), &frame_len);
        uint16_t status = MIDWARE_STATUS_OK;
        if (codec_rc == MIDWARE_CAMERA_ERR_UNSUPPORTED_COMMAND) {
            status = MIDWARE_STATUS_UNSUPPORTED_COMMAND;
        } else if (codec_rc == MIDWARE_CAMERA_ERR_INVALID_PARAMS ||
                   codec_rc == MIDWARE_CAMERA_ERR_BUFFER_TOO_SMALL) {
            status = MIDWARE_STATUS_INVALID_PARAM;
        } else if (codec_rc != 0) {
            status = MIDWARE_STATUS_DEVICE_ERROR;
        }

        int32_t sent = midware_feedback_send(feedback_conn,
                                             command.device_type,
                                             command.command_type,
                                             MIDWARE_FEEDBACK_ACK,
                                             status,
                                             command.request_timestamp_us,
                                             MIDWARE_DATA_NONE,
                                             NULL,
                                             0);
        if (sent <= 0) {
            fprintf(stderr, "send feedback failed at index %d: %d\n", i, sent);
            ok = 0;
            break;
        }

        printf("BOARD_MOCK index=%d command_device=0x%04X command_type=0x%04X frame_len=%u status=%u request_ts=%llu\n",
               i,
               command.device_type,
               command.command_type,
               frame_len,
               status,
               (unsigned long long)command.request_timestamp_us);
        fflush(stdout);

        if (status != MIDWARE_STATUS_OK) {
            ok = 0;
        }
    }

    midware_tcp_conn_close(feedback_conn);
    midware_tcp_conn_close(command_conn);
    return ok ? 0 : 1;
}
