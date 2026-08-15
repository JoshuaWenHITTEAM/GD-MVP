#ifndef MIDWARE_NET_H
#define MIDWARE_NET_H

#include <stdint.h>
#include "midware_packet.h"

#ifdef __cplusplus
extern "C" {
#endif

#define MIDWARE_NET_DEFAULT_MAX_FRAME_LENGTH (16 * 1024 * 1024)

#define MIDWARE_NET_ERR_SOCKET (-1)
#define MIDWARE_NET_ERR_PACKET (-2)
#define MIDWARE_NET_ERR_CLOSED (-3)

typedef struct midware_udp_socket midware_udp_socket_t;
typedef struct midware_tcp_server midware_tcp_server_t;
typedef struct midware_tcp_conn midware_tcp_conn_t;

midware_udp_socket_t* midware_udp_open(const char* bind_host, uint16_t bind_port, int timeout_ms);
void midware_udp_close(midware_udp_socket_t* sock);
int32_t midware_udp_local_port(midware_udp_socket_t* sock);

int32_t midware_udp_send(midware_udp_socket_t* sock,
                         const char* host,
                         uint16_t port,
                         const void* data,
                         uint32_t len);
int32_t midware_udp_recv(midware_udp_socket_t* sock,
                         void* buf,
                         int32_t max_len,
                         char* out_host,
                         int32_t out_host_len,
                         uint16_t* out_port);

int32_t midware_udp_send_packet(midware_udp_socket_t* sock,
                                const char* host,
                                uint16_t port,
                                uint8_t type,
                                uint64_t timestamp_us,
                                const void* payload,
                                uint32_t payload_len);
int32_t midware_udp_recv_packet(midware_udp_socket_t* sock,
                                void* buf,
                                int32_t max_len,
                                midware_packet_header_t* out_header,
                                const void** out_payload,
                                char* out_host,
                                int32_t out_host_len,
                                uint16_t* out_port);

midware_tcp_conn_t* midware_tcp_connect(const char* host, uint16_t port, int timeout_ms);
midware_tcp_server_t* midware_tcp_listen(const char* bind_host,
                                         uint16_t bind_port,
                                         int backlog,
                                         int timeout_ms);
midware_tcp_conn_t* midware_tcp_accept(midware_tcp_server_t* server);
void midware_tcp_conn_close(midware_tcp_conn_t* conn);
void midware_tcp_server_close(midware_tcp_server_t* server);
int32_t midware_tcp_server_port(midware_tcp_server_t* server);

int32_t midware_tcp_send_packet_bytes(midware_tcp_conn_t* conn,
                                      const void* packet,
                                      uint32_t packet_len);
int32_t midware_tcp_send_packet(midware_tcp_conn_t* conn,
                                uint8_t type,
                                uint64_t timestamp_us,
                                const void* payload,
                                uint32_t payload_len);
int32_t midware_tcp_read_packet_bytes(midware_tcp_conn_t* conn,
                                      void* buf,
                                      int32_t max_len,
                                      uint32_t max_frame_length);
int32_t midware_tcp_read_packet(midware_tcp_conn_t* conn,
                                void* buf,
                                int32_t max_len,
                                uint32_t max_frame_length,
                                midware_packet_header_t* out_header,
                                const void** out_payload);

#ifdef __cplusplus
}
#endif

#endif // MIDWARE_NET_H
