#include "midware_net.h"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <netdb.h>
#include <poll.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#ifndef MSG_NOSIGNAL
#define MSG_NOSIGNAL 0
#endif

#ifndef MSG_TRUNC
#define MSG_TRUNC 0
#endif

struct midware_udp_socket {
    int fd;
    int timeout_ms;
};

struct midware_tcp_server {
    int fd;
    int timeout_ms;
};

struct midware_tcp_conn {
    int fd;
    int timeout_ms;
};

static int64_t monotonic_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

static int remaining_timeout_ms(int timeout_ms, int64_t deadline_ms) {
    if (timeout_ms < 0) {
        return -1;
    }
    int64_t now = monotonic_ms();
    if (now >= deadline_ms) {
        return 0;
    }
    int64_t remaining = deadline_ms - now;
    return remaining > INT_MAX ? INT_MAX : (int)remaining;
}

static int wait_fd(int fd, short events, int timeout_ms) {
    struct pollfd pfd;
    pfd.fd = fd;
    pfd.events = events;
    pfd.revents = 0;

    for (;;) {
        int rc = poll(&pfd, 1, timeout_ms);
        if (rc < 0 && errno == EINTR) {
            continue;
        }
        if (rc <= 0) {
            return rc;
        }
        if (pfd.revents & (POLLERR | POLLNVAL)) {
            errno = ECONNRESET;
            return MIDWARE_NET_ERR_SOCKET;
        }
        return 1;
    }
}

static void close_fd(int fd) {
    if (fd >= 0) {
        close(fd);
    }
}

static int set_nonblocking(int fd, bool nonblocking, int* old_flags) {
    int flags = fcntl(fd, F_GETFL, 0);
    if (flags < 0) {
        return -1;
    }
    if (old_flags) {
        *old_flags = flags;
    }

    int new_flags = nonblocking ? (flags | O_NONBLOCK) : (flags & ~O_NONBLOCK);
    if (fcntl(fd, F_SETFL, new_flags) < 0) {
        return -1;
    }
    return 0;
}

static uint32_t read_be32(const uint8_t* ptr) {
    return ((uint32_t)ptr[0] << 24) |
           ((uint32_t)ptr[1] << 16) |
           ((uint32_t)ptr[2] << 8) |
           (uint32_t)ptr[3];
}

static int socket_family(int fd) {
    struct sockaddr_storage ss;
    socklen_t len = sizeof(ss);
    if (getsockname(fd, (struct sockaddr*)&ss, &len) < 0) {
        return AF_UNSPEC;
    }
    return ss.ss_family;
}

static int write_host_port(const struct sockaddr_storage* addr,
                           socklen_t addr_len,
                           char* out_host,
                           int32_t out_host_len,
                           uint16_t* out_port) {
    (void)addr_len;
    if (!addr) {
        return MIDWARE_NET_ERR_SOCKET;
    }

    void* src = NULL;
    uint16_t port = 0;
    if (addr->ss_family == AF_INET) {
        const struct sockaddr_in* in = (const struct sockaddr_in*)addr;
        src = (void*)&in->sin_addr;
        port = ntohs(in->sin_port);
    } else if (addr->ss_family == AF_INET6) {
        const struct sockaddr_in6* in6 = (const struct sockaddr_in6*)addr;
        src = (void*)&in6->sin6_addr;
        port = ntohs(in6->sin6_port);
    } else {
        errno = EAFNOSUPPORT;
        return MIDWARE_NET_ERR_SOCKET;
    }

    if (out_host && out_host_len > 0) {
        if (!inet_ntop(addr->ss_family, src, out_host, (socklen_t)out_host_len)) {
            return MIDWARE_NET_ERR_SOCKET;
        }
    }
    if (out_port) {
        *out_port = port;
    }
    return 0;
}

static int resolve_addr(const char* host,
                        uint16_t port,
                        int socktype,
                        int family,
                        int flags,
                        struct addrinfo** out) {
    char service[16];
    snprintf(service, sizeof(service), "%u", (unsigned)port);

    struct addrinfo hints;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = family;
    hints.ai_socktype = socktype;
    hints.ai_flags = flags;

    const char* node = (host && host[0] != '\0') ? host : NULL;
    int rc = getaddrinfo(node, service, &hints, out);
    if (rc != 0) {
        errno = EINVAL;
        return MIDWARE_NET_ERR_SOCKET;
    }
    return 0;
}

midware_udp_socket_t* midware_udp_open(const char* bind_host, uint16_t bind_port, int timeout_ms) {
    struct addrinfo* res = NULL;
    int flags = AI_PASSIVE;
    if (resolve_addr(bind_host, bind_port, SOCK_DGRAM, AF_UNSPEC, flags, &res) < 0) {
        return NULL;
    }

    int fd = -1;
    for (struct addrinfo* ai = res; ai != NULL; ai = ai->ai_next) {
        fd = socket(ai->ai_family, ai->ai_socktype, ai->ai_protocol);
        if (fd < 0) {
            continue;
        }
        int yes = 1;
        setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
        if (bind(fd, ai->ai_addr, ai->ai_addrlen) == 0) {
            break;
        }
        close_fd(fd);
        fd = -1;
    }
    freeaddrinfo(res);

    if (fd < 0) {
        return NULL;
    }

    midware_udp_socket_t* sock = (midware_udp_socket_t*)calloc(1, sizeof(midware_udp_socket_t));
    if (!sock) {
        close_fd(fd);
        return NULL;
    }
    sock->fd = fd;
    sock->timeout_ms = timeout_ms;
    return sock;
}

void midware_udp_close(midware_udp_socket_t* sock) {
    if (!sock) {
        return;
    }
    close_fd(sock->fd);
    free(sock);
}

int32_t midware_udp_local_port(midware_udp_socket_t* sock) {
    if (!sock) {
        return MIDWARE_NET_ERR_SOCKET;
    }
    struct sockaddr_storage ss;
    socklen_t len = sizeof(ss);
    if (getsockname(sock->fd, (struct sockaddr*)&ss, &len) < 0) {
        return MIDWARE_NET_ERR_SOCKET;
    }
    if (ss.ss_family == AF_INET) {
        return ntohs(((struct sockaddr_in*)&ss)->sin_port);
    }
    if (ss.ss_family == AF_INET6) {
        return ntohs(((struct sockaddr_in6*)&ss)->sin6_port);
    }
    errno = EAFNOSUPPORT;
    return MIDWARE_NET_ERR_SOCKET;
}

int32_t midware_udp_send(midware_udp_socket_t* sock,
                         const char* host,
                         uint16_t port,
                         const void* data,
                         uint32_t len) {
    if (!sock || !host || (!data && len > 0) || len > INT32_MAX) {
        errno = EINVAL;
        return MIDWARE_NET_ERR_SOCKET;
    }

    int ready = wait_fd(sock->fd, POLLOUT, sock->timeout_ms);
    if (ready <= 0) {
        return ready;
    }

    int family = socket_family(sock->fd);
    struct addrinfo* res = NULL;
    if (resolve_addr(host, port, SOCK_DGRAM, family, 0, &res) < 0) {
        return MIDWARE_NET_ERR_SOCKET;
    }

    int32_t sent = MIDWARE_NET_ERR_SOCKET;
    for (struct addrinfo* ai = res; ai != NULL; ai = ai->ai_next) {
        ssize_t n = sendto(sock->fd, data, len, 0, ai->ai_addr, ai->ai_addrlen);
        if (n >= 0) {
            sent = (int32_t)n;
            break;
        }
        if (errno == EINTR) {
            continue;
        }
    }
    freeaddrinfo(res);
    return sent;
}

int32_t midware_udp_recv(midware_udp_socket_t* sock,
                         void* buf,
                         int32_t max_len,
                         char* out_host,
                         int32_t out_host_len,
                         uint16_t* out_port) {
    if (!sock || max_len < 0 || (!buf && max_len > 0)) {
        errno = EINVAL;
        return MIDWARE_NET_ERR_SOCKET;
    }

    int ready = wait_fd(sock->fd, POLLIN, sock->timeout_ms);
    if (ready <= 0) {
        return ready;
    }

    char tmp[1];
    struct sockaddr_storage addr;
    socklen_t addr_len = sizeof(addr);
    ssize_t needed;
    do {
        needed = recvfrom(sock->fd,
                          tmp,
                          sizeof(tmp),
                          MSG_PEEK | MSG_TRUNC,
                          (struct sockaddr*)&addr,
                          &addr_len);
    } while (needed < 0 && errno == EINTR);

    if (needed < 0) {
        return MIDWARE_NET_ERR_SOCKET;
    }
    if (needed > max_len) {
        return (int32_t)needed;
    }

    addr_len = sizeof(addr);
    ssize_t n;
    do {
        n = recvfrom(sock->fd,
                     buf,
                     (size_t)max_len,
                     0,
                     (struct sockaddr*)&addr,
                     &addr_len);
    } while (n < 0 && errno == EINTR);

    if (n < 0) {
        return MIDWARE_NET_ERR_SOCKET;
    }
    if (write_host_port(&addr, addr_len, out_host, out_host_len, out_port) < 0) {
        return MIDWARE_NET_ERR_SOCKET;
    }
    return (int32_t)n;
}

int32_t midware_udp_send_packet(midware_udp_socket_t* sock,
                                const char* host,
                                uint16_t port,
                                uint8_t type,
                                uint64_t timestamp_us,
                                const void* payload,
                                uint32_t payload_len) {
    uint32_t total_size = midware_packet_size(payload_len);
    if (total_size > INT32_MAX) {
        errno = EINVAL;
        return MIDWARE_NET_ERR_SOCKET;
    }

    uint8_t* packet = (uint8_t*)malloc(total_size);
    if (!packet) {
        return MIDWARE_NET_ERR_SOCKET;
    }
    int32_t serialized = midware_packet_serialize(packet,
                                                  (int32_t)total_size,
                                                  type,
                                                  timestamp_us,
                                                  payload,
                                                  payload_len);
    if (serialized < 0) {
        free(packet);
        return MIDWARE_NET_ERR_PACKET;
    }

    int32_t sent = midware_udp_send(sock, host, port, packet, (uint32_t)serialized);
    free(packet);
    return sent;
}

int32_t midware_udp_recv_packet(midware_udp_socket_t* sock,
                                void* buf,
                                int32_t max_len,
                                midware_packet_header_t* out_header,
                                const void** out_payload,
                                char* out_host,
                                int32_t out_host_len,
                                uint16_t* out_port) {
    int32_t len = midware_udp_recv(sock, buf, max_len, out_host, out_host_len, out_port);
    if (len <= 0 || len > max_len) {
        return len;
    }
    if (!midware_packet_parse(buf, len, out_header, out_payload)) {
        return MIDWARE_NET_ERR_PACKET;
    }
    return len;
}

static int connect_with_timeout(int fd, const struct sockaddr* addr, socklen_t addrlen, int timeout_ms) {
    int old_flags = 0;
    if (set_nonblocking(fd, true, &old_flags) < 0) {
        return MIDWARE_NET_ERR_SOCKET;
    }

    int rc = connect(fd, addr, addrlen);
    if (rc == 0) {
        fcntl(fd, F_SETFL, old_flags);
        return 0;
    }
    if (errno != EINPROGRESS) {
        fcntl(fd, F_SETFL, old_flags);
        return MIDWARE_NET_ERR_SOCKET;
    }

    rc = wait_fd(fd, POLLOUT, timeout_ms);
    if (rc <= 0) {
        fcntl(fd, F_SETFL, old_flags);
        return rc;
    }

    int err = 0;
    socklen_t err_len = sizeof(err);
    if (getsockopt(fd, SOL_SOCKET, SO_ERROR, &err, &err_len) < 0 || err != 0) {
        errno = err != 0 ? err : errno;
        fcntl(fd, F_SETFL, old_flags);
        return MIDWARE_NET_ERR_SOCKET;
    }

    fcntl(fd, F_SETFL, old_flags);
    return 0;
}

midware_tcp_conn_t* midware_tcp_connect(const char* host, uint16_t port, int timeout_ms) {
    if (!host) {
        errno = EINVAL;
        return NULL;
    }

    struct addrinfo* res = NULL;
    if (resolve_addr(host, port, SOCK_STREAM, AF_UNSPEC, 0, &res) < 0) {
        return NULL;
    }

    int fd = -1;
    for (struct addrinfo* ai = res; ai != NULL; ai = ai->ai_next) {
        fd = socket(ai->ai_family, ai->ai_socktype, ai->ai_protocol);
        if (fd < 0) {
            continue;
        }
        int rc = connect_with_timeout(fd, ai->ai_addr, ai->ai_addrlen, timeout_ms);
        if (rc == 0) {
            break;
        }
        close_fd(fd);
        fd = -1;
    }
    freeaddrinfo(res);

    if (fd < 0) {
        return NULL;
    }

    midware_tcp_conn_t* conn = (midware_tcp_conn_t*)calloc(1, sizeof(midware_tcp_conn_t));
    if (!conn) {
        close_fd(fd);
        return NULL;
    }
    conn->fd = fd;
    conn->timeout_ms = timeout_ms;
    return conn;
}

midware_tcp_server_t* midware_tcp_listen(const char* bind_host,
                                         uint16_t bind_port,
                                         int backlog,
                                         int timeout_ms) {
    struct addrinfo* res = NULL;
    if (resolve_addr(bind_host, bind_port, SOCK_STREAM, AF_UNSPEC, AI_PASSIVE, &res) < 0) {
        return NULL;
    }

    int fd = -1;
    for (struct addrinfo* ai = res; ai != NULL; ai = ai->ai_next) {
        fd = socket(ai->ai_family, ai->ai_socktype, ai->ai_protocol);
        if (fd < 0) {
            continue;
        }
        int yes = 1;
        setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
        if (bind(fd, ai->ai_addr, ai->ai_addrlen) == 0 &&
                listen(fd, backlog > 0 ? backlog : 16) == 0) {
            break;
        }
        close_fd(fd);
        fd = -1;
    }
    freeaddrinfo(res);

    if (fd < 0) {
        return NULL;
    }

    midware_tcp_server_t* server = (midware_tcp_server_t*)calloc(1, sizeof(midware_tcp_server_t));
    if (!server) {
        close_fd(fd);
        return NULL;
    }
    server->fd = fd;
    server->timeout_ms = timeout_ms;
    return server;
}

midware_tcp_conn_t* midware_tcp_accept(midware_tcp_server_t* server) {
    if (!server) {
        errno = EINVAL;
        return NULL;
    }

    int ready = wait_fd(server->fd, POLLIN, server->timeout_ms);
    if (ready <= 0) {
        return NULL;
    }

    int fd;
    do {
        fd = accept(server->fd, NULL, NULL);
    } while (fd < 0 && errno == EINTR);

    if (fd < 0) {
        return NULL;
    }

    midware_tcp_conn_t* conn = (midware_tcp_conn_t*)calloc(1, sizeof(midware_tcp_conn_t));
    if (!conn) {
        close_fd(fd);
        return NULL;
    }
    conn->fd = fd;
    conn->timeout_ms = server->timeout_ms;
    return conn;
}

void midware_tcp_conn_close(midware_tcp_conn_t* conn) {
    if (!conn) {
        return;
    }
    close_fd(conn->fd);
    free(conn);
}

void midware_tcp_server_close(midware_tcp_server_t* server) {
    if (!server) {
        return;
    }
    close_fd(server->fd);
    free(server);
}

int32_t midware_tcp_server_port(midware_tcp_server_t* server) {
    if (!server) {
        errno = EINVAL;
        return MIDWARE_NET_ERR_SOCKET;
    }
    struct sockaddr_storage ss;
    socklen_t len = sizeof(ss);
    if (getsockname(server->fd, (struct sockaddr*)&ss, &len) < 0) {
        return MIDWARE_NET_ERR_SOCKET;
    }
    if (ss.ss_family == AF_INET) {
        return ntohs(((struct sockaddr_in*)&ss)->sin_port);
    }
    if (ss.ss_family == AF_INET6) {
        return ntohs(((struct sockaddr_in6*)&ss)->sin6_port);
    }
    errno = EAFNOSUPPORT;
    return MIDWARE_NET_ERR_SOCKET;
}

static int32_t send_all(midware_tcp_conn_t* conn, const uint8_t* data, uint32_t len) {
    int64_t deadline_ms = conn->timeout_ms >= 0 ? monotonic_ms() + conn->timeout_ms : 0;
    uint32_t offset = 0;

    while (offset < len) {
        int wait_ms = remaining_timeout_ms(conn->timeout_ms, deadline_ms);
        int ready = wait_fd(conn->fd, POLLOUT, wait_ms);
        if (ready <= 0) {
            return ready;
        }

        ssize_t n = send(conn->fd, data + offset, len - offset, MSG_NOSIGNAL);
        if (n > 0) {
            offset += (uint32_t)n;
            continue;
        }
        if (n == 0) {
            return MIDWARE_NET_ERR_CLOSED;
        }
        if (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK) {
            continue;
        }
        if (errno == EPIPE || errno == ECONNRESET) {
            return MIDWARE_NET_ERR_CLOSED;
        }
        return MIDWARE_NET_ERR_SOCKET;
    }

    return (int32_t)len;
}

int32_t midware_tcp_send_packet_bytes(midware_tcp_conn_t* conn,
                                      const void* packet,
                                      uint32_t packet_len) {
    if (!conn || (!packet && packet_len > 0) || packet_len > INT32_MAX) {
        errno = EINVAL;
        return MIDWARE_NET_ERR_SOCKET;
    }
    midware_packet_header_t header;
    if (!midware_packet_parse(packet, (int32_t)packet_len, &header, NULL) ||
            packet_len != midware_packet_size(header.payload_len)) {
        return MIDWARE_NET_ERR_PACKET;
    }
    return send_all(conn, (const uint8_t*)packet, packet_len);
}

int32_t midware_tcp_send_packet(midware_tcp_conn_t* conn,
                                uint8_t type,
                                uint64_t timestamp_us,
                                const void* payload,
                                uint32_t payload_len) {
    uint32_t total_size = midware_packet_size(payload_len);
    if (total_size > INT32_MAX) {
        errno = EINVAL;
        return MIDWARE_NET_ERR_SOCKET;
    }

    uint8_t* packet = (uint8_t*)malloc(total_size);
    if (!packet) {
        return MIDWARE_NET_ERR_SOCKET;
    }
    int32_t serialized = midware_packet_serialize(packet,
                                                  (int32_t)total_size,
                                                  type,
                                                  timestamp_us,
                                                  payload,
                                                  payload_len);
    if (serialized < 0) {
        free(packet);
        return MIDWARE_NET_ERR_PACKET;
    }

    int32_t sent = midware_tcp_send_packet_bytes(conn, packet, (uint32_t)serialized);
    free(packet);
    return sent;
}

static int available_bytes(int fd, int* out_available) {
    int available = 0;
    if (ioctl(fd, FIONREAD, &available) < 0) {
        return MIDWARE_NET_ERR_SOCKET;
    }
    *out_available = available;
    return 0;
}

static int wait_available(midware_tcp_conn_t* conn,
                          int min_available,
                          int64_t deadline_ms,
                          int* out_available) {
    for (;;) {
        if (available_bytes(conn->fd, out_available) < 0) {
            return MIDWARE_NET_ERR_SOCKET;
        }
        if (*out_available >= min_available) {
            return 1;
        }

        int wait_ms = remaining_timeout_ms(conn->timeout_ms, deadline_ms);
        int ready = wait_fd(conn->fd, POLLIN, wait_ms);
        if (ready == 0) {
            return 0;
        }
        if (ready < 0) {
            return ready;
        }

        if (available_bytes(conn->fd, out_available) < 0) {
            return MIDWARE_NET_ERR_SOCKET;
        }
        if (*out_available >= min_available) {
            return 1;
        }

        char tmp;
        ssize_t n = recv(conn->fd, &tmp, 1, MSG_PEEK);
        if (n == 0) {
            return MIDWARE_NET_ERR_CLOSED;
        }
        if (n < 0 && errno != EINTR && errno != EAGAIN && errno != EWOULDBLOCK) {
            return MIDWARE_NET_ERR_SOCKET;
        }
    }
}

static int32_t recv_exact(midware_tcp_conn_t* conn,
                          uint8_t* buf,
                          uint32_t len,
                          int64_t deadline_ms) {
    uint32_t offset = 0;
    while (offset < len) {
        int wait_ms = remaining_timeout_ms(conn->timeout_ms, deadline_ms);
        int ready = wait_fd(conn->fd, POLLIN, wait_ms);
        if (ready <= 0) {
            return ready;
        }

        ssize_t n = recv(conn->fd, buf + offset, len - offset, 0);
        if (n > 0) {
            offset += (uint32_t)n;
            continue;
        }
        if (n == 0) {
            return MIDWARE_NET_ERR_CLOSED;
        }
        if (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK) {
            continue;
        }
        if (errno == ECONNRESET) {
            return MIDWARE_NET_ERR_CLOSED;
        }
        return MIDWARE_NET_ERR_SOCKET;
    }
    return (int32_t)len;
}

int32_t midware_tcp_read_packet_bytes(midware_tcp_conn_t* conn,
                                      void* buf,
                                      int32_t max_len,
                                      uint32_t max_frame_length) {
    if (!conn || max_len < 0 || (!buf && max_len > 0)) {
        errno = EINVAL;
        return MIDWARE_NET_ERR_SOCKET;
    }
    if (max_frame_length == 0) {
        max_frame_length = MIDWARE_NET_DEFAULT_MAX_FRAME_LENGTH;
    }

    int64_t deadline_ms = conn->timeout_ms >= 0 ? monotonic_ms() + conn->timeout_ms : 0;
    int available = 0;
    int ready = wait_available(conn, MIDWARE_HEADER_SIZE, deadline_ms, &available);
    if (ready <= 0) {
        return ready;
    }

    uint8_t header[MIDWARE_HEADER_SIZE];
    ssize_t n;
    do {
        n = recv(conn->fd, header, sizeof(header), MSG_PEEK);
    } while (n < 0 && errno == EINTR);

    if (n == 0) {
        return MIDWARE_NET_ERR_CLOSED;
    }
    if (n < (ssize_t)sizeof(header)) {
        return n < 0 ? MIDWARE_NET_ERR_SOCKET : 0;
    }

    uint32_t payload_len = read_be32(header + 9);
    uint32_t total_len = midware_packet_size(payload_len);
    if (total_len < MIDWARE_HEADER_SIZE || total_len > max_frame_length || total_len > INT32_MAX) {
        return MIDWARE_NET_ERR_PACKET;
    }
    if (total_len > (uint32_t)max_len) {
        return (int32_t)total_len;
    }

    ready = wait_available(conn, (int)total_len, deadline_ms, &available);
    if (ready <= 0) {
        return ready;
    }

    return recv_exact(conn, (uint8_t*)buf, total_len, deadline_ms);
}

int32_t midware_tcp_read_packet(midware_tcp_conn_t* conn,
                                void* buf,
                                int32_t max_len,
                                uint32_t max_frame_length,
                                midware_packet_header_t* out_header,
                                const void** out_payload) {
    int32_t len = midware_tcp_read_packet_bytes(conn, buf, max_len, max_frame_length);
    if (len <= 0 || len > max_len) {
        return len;
    }
    if (!midware_packet_parse(buf, len, out_header, out_payload)) {
        return MIDWARE_NET_ERR_PACKET;
    }
    return len;
}
