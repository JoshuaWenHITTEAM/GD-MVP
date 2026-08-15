#include "midware_net.h"
#include "midware_packet.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static void fail(const char* msg) {
    fprintf(stderr, "FAIL: %s\n", msg);
    exit(1);
}

static void expect_int(const char* msg, int32_t actual, int32_t expected) {
    if (actual != expected) {
        fprintf(stderr, "FAIL: %s: actual=%d expected=%d\n", msg, actual, expected);
        exit(1);
    }
}

static int32_t build_packet(uint8_t* buf,
                            int32_t buf_len,
                            uint8_t type,
                            uint64_t ts,
                            const char* payload) {
    int32_t len = midware_packet_serialize(buf,
                                           buf_len,
                                           type,
                                           ts,
                                           payload,
                                           (uint32_t)strlen(payload));
    if (len <= 0) {
        fail("packet serialize");
    }
    return len;
}

static void test_udp(void) {
    midware_udp_socket_t* recv_sock = midware_udp_open("127.0.0.1", 0, 1000);
    midware_udp_socket_t* send_sock = midware_udp_open("127.0.0.1", 0, 1000);
    if (!recv_sock || !send_sock) {
        fail("udp open");
    }

    int32_t port = midware_udp_local_port(recv_sock);
    if (port <= 0) {
        fail("udp local port");
    }

    const char* raw = "udp raw datagram";
    expect_int("udp send raw",
               midware_udp_send(send_sock, "127.0.0.1", (uint16_t)port, raw, strlen(raw)),
               (int32_t)strlen(raw));

    char buf[256];
    char host[64];
    uint16_t from_port = 0;
    int32_t len = midware_udp_recv(recv_sock, buf, sizeof(buf), host, sizeof(host), &from_port);
    expect_int("udp recv raw len", len, (int32_t)strlen(raw));
    if (memcmp(buf, raw, strlen(raw)) != 0 || from_port == 0) {
        fail("udp recv raw payload/source");
    }

    const char* payload = "udp packet payload";
    len = midware_udp_send_packet(send_sock,
                                  "127.0.0.1",
                                  (uint16_t)port,
                                  1,
                                  123456,
                                  payload,
                                  (uint32_t)strlen(payload));
    expect_int("udp send packet len", len, MIDWARE_HEADER_SIZE + (int32_t)strlen(payload));

    midware_packet_header_t header;
    const void* payload_ptr = NULL;
    len = midware_udp_recv_packet(recv_sock,
                                  buf,
                                  sizeof(buf),
                                  &header,
                                  &payload_ptr,
                                  NULL,
                                  0,
                                  NULL);
    expect_int("udp recv packet len", len, MIDWARE_HEADER_SIZE + (int32_t)strlen(payload));
    if (header.type != 1 || header.timestamp_us != 123456 ||
            header.payload_len != strlen(payload) ||
            memcmp(payload_ptr, payload, strlen(payload)) != 0) {
        fail("udp packet parse");
    }

    midware_udp_close(send_sock);
    midware_udp_close(recv_sock);
    printf("UDP network test passed\n");
}

static void tcp_server_child(midware_tcp_server_t* server) {
    midware_tcp_conn_t* conn = midware_tcp_accept(server);
    if (!conn) {
        fail("tcp accept");
    }
    midware_tcp_server_close(server);

    uint8_t buf[256];
    midware_packet_header_t header;
    const void* payload_ptr = NULL;

    int32_t len = midware_tcp_read_packet(conn,
                                          buf,
                                          sizeof(buf),
                                          MIDWARE_NET_DEFAULT_MAX_FRAME_LENGTH,
                                          &header,
                                          &payload_ptr);
    if (len <= 0 || header.type != 1 || header.timestamp_us != 111 ||
            header.payload_len != strlen("tcp one") ||
            memcmp(payload_ptr, "tcp one", strlen("tcp one")) != 0) {
        fail("tcp first packet");
    }

    len = midware_tcp_read_packet(conn,
                                  buf,
                                  sizeof(buf),
                                  MIDWARE_NET_DEFAULT_MAX_FRAME_LENGTH,
                                  &header,
                                  &payload_ptr);
    if (len <= 0 || header.type != 2 || header.timestamp_us != 222 ||
            header.payload_len != strlen("tcp two") ||
            memcmp(payload_ptr, "tcp two", strlen("tcp two")) != 0) {
        fail("tcp second packet");
    }

    uint8_t small[8];
    int32_t needed = midware_tcp_read_packet_bytes(conn,
                                                   small,
                                                   sizeof(small),
                                                   MIDWARE_NET_DEFAULT_MAX_FRAME_LENGTH);
    if (needed <= (int32_t)sizeof(small)) {
        fail("tcp small buffer required length");
    }

    len = midware_tcp_read_packet(conn,
                                  buf,
                                  sizeof(buf),
                                  MIDWARE_NET_DEFAULT_MAX_FRAME_LENGTH,
                                  &header,
                                  &payload_ptr);
    if (len != needed || header.type != 3 || header.timestamp_us != 333 ||
            header.payload_len != strlen("tcp packet that needs a larger read buffer") ||
            memcmp(payload_ptr,
                   "tcp packet that needs a larger read buffer",
                   strlen("tcp packet that needs a larger read buffer")) != 0) {
        fail("tcp read after small buffer");
    }

    len = midware_tcp_read_packet_bytes(conn,
                                        buf,
                                        sizeof(buf),
                                        MIDWARE_NET_DEFAULT_MAX_FRAME_LENGTH);
    expect_int("tcp closed", len, MIDWARE_NET_ERR_CLOSED);
    midware_tcp_conn_close(conn);
    exit(0);
}

static void test_tcp(void) {
    midware_tcp_server_t* server = midware_tcp_listen("127.0.0.1", 0, 16, 2000);
    if (!server) {
        fail("tcp listen");
    }
    int32_t port = midware_tcp_server_port(server);
    if (port <= 0) {
        fail("tcp server port");
    }

    fflush(stdout);
    pid_t pid = fork();
    if (pid < 0) {
        fail("fork");
    }
    if (pid == 0) {
        tcp_server_child(server);
    }

    usleep(100000);
    midware_tcp_server_close(server);

    midware_tcp_conn_t* conn = midware_tcp_connect("127.0.0.1", (uint16_t)port, 2000);
    if (!conn) {
        fail("tcp connect");
    }

    uint8_t packet[256];
    int32_t len = build_packet(packet, sizeof(packet), 1, 111, "tcp one");
    expect_int("tcp send first", midware_tcp_send_packet_bytes(conn, packet, (uint32_t)len), len);

    len = build_packet(packet, sizeof(packet), 2, 222, "tcp two");
    expect_int("tcp send second", midware_tcp_send_packet_bytes(conn, packet, (uint32_t)len), len);

    len = build_packet(packet,
                       sizeof(packet),
                       3,
                       333,
                       "tcp packet that needs a larger read buffer");
    expect_int("tcp send third", midware_tcp_send_packet_bytes(conn, packet, (uint32_t)len), len);

    midware_tcp_conn_close(conn);

    int status = 0;
    waitpid(pid, &status, 0);
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        fail("tcp child status");
    }
    printf("TCP network test passed\n");
}

int main(void) {
    test_udp();
    test_tcp();
    printf("Network SDK test passed\n");
    return 0;
}
