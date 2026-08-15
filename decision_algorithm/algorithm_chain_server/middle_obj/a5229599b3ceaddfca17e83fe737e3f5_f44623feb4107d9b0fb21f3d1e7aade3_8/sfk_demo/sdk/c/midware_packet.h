#ifndef MIDWARE_PACKET_H
#define MIDWARE_PACKET_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// Packet header structure
typedef struct {
    uint8_t type;           // 1 Byte
    uint64_t timestamp_us;  // 8 Bytes
    uint32_t payload_len;   // 4 Bytes
} midware_packet_header_t;

// Constants
#define MIDWARE_HEADER_SIZE 13
#define MIDWARE_TYPE_HIGH_FREQ 0
#define MIDWARE_TYPE_LOW_FREQ 1
#define MIDWARE_TYPE_IMAGE_FRAME 2
#define MIDWARE_TYPE_RDMA_IMAGE_RAW 3

/**
 * Calculate the total buffer size needed for a packet.
 */
static inline uint32_t midware_packet_size(uint32_t payload_len) {
    return MIDWARE_HEADER_SIZE + payload_len;
}

/**
 * Serialize header and payload into a raw buffer.
 * 
 * Wire format: [Type(1)] [Ts(8 BE)] [Len(4 BE)] [Payload(N)]
 * 
 * @param buffer [OUT] Output buffer (must be at least midware_packet_size(payload_len))
 * @param buf_capacity Capacity of the buffer for safety check
 * @param type Data type
 * @param timestamp_us Timestamp
 * @param payload Source payload pointer (can be NULL if payload_len is 0)
 * @param payload_len Length of payload
 * @return Number of bytes written, or -1 on error (buffer too small)
 */
int32_t midware_packet_serialize(void* buffer,
                                int32_t buf_capacity,
                                uint8_t type, 
                                uint64_t timestamp_us, 
                                const void* payload, 
                                uint32_t payload_len);

/**
 * Serialize only the header into a buffer. 
 * Useful if you want to write header first, then write payload directly (scatter/gather).
 */
int32_t midware_packet_serialize_header(void* buffer,
                                       int32_t buf_capacity,
                                       uint8_t type, 
                                       uint64_t timestamp_us, 
                                       uint32_t payload_len);

/**
 * Parse a raw blob into header and payload pointer.
 * Pure memory operation.
 */
bool midware_packet_parse(const void* raw_data, 
                         int32_t total_len, 
                         midware_packet_header_t* out_header, 
                         const void** out_payload);

#ifdef __cplusplus
}
#endif

#endif // MIDWARE_PACKET_H
