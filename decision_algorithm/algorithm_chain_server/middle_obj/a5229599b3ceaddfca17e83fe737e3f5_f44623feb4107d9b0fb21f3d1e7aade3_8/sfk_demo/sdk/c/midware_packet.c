#include "midware_packet.h"
#include <string.h>
#include <endian.h>
#include <stdlib.h>

// Helper to write Big Endian
static inline void write_be64(uint8_t* ptr, uint64_t val) {
    ptr[0] = (val >> 56) & 0xFF;
    ptr[1] = (val >> 48) & 0xFF;
    ptr[2] = (val >> 40) & 0xFF;
    ptr[3] = (val >> 32) & 0xFF;
    ptr[4] = (val >> 24) & 0xFF;
    ptr[5] = (val >> 16) & 0xFF;
    ptr[6] = (val >> 8) & 0xFF;
    ptr[7] = (val) & 0xFF;
}

static inline void write_be32(uint8_t* ptr, uint32_t val) {
    ptr[0] = (val >> 24) & 0xFF;
    ptr[1] = (val >> 16) & 0xFF;
    ptr[2] = (val >> 8) & 0xFF;
    ptr[3] = (val) & 0xFF;
}

static inline uint64_t read_be64(const uint8_t* ptr) {
    return ((uint64_t)ptr[0] << 56) | ((uint64_t)ptr[1] << 48) |
           ((uint64_t)ptr[2] << 40) | ((uint64_t)ptr[3] << 32) |
           ((uint64_t)ptr[4] << 24) | ((uint64_t)ptr[5] << 16) |
           ((uint64_t)ptr[6] << 8)  | (uint64_t)ptr[7];
}

static inline uint32_t read_be32(const uint8_t* ptr) {
    return ((uint32_t)ptr[0] << 24) |
           ((uint32_t)ptr[1] << 16) |
           ((uint32_t)ptr[2] << 8) |
           (uint32_t)ptr[3];
}

int32_t midware_packet_serialize(void* buffer,
                                int32_t buf_capacity,
                                uint8_t type, 
                                uint64_t timestamp_us, 
                                const void* payload, 
                                uint32_t payload_len) {
    if (!buffer) return -1;
    
    int32_t needed = MIDWARE_HEADER_SIZE + payload_len;
    if (buf_capacity < needed) return -1;
    
    uint8_t* ptr = (uint8_t*)buffer;
    
    // Header
    ptr[0] = type;
    write_be64(ptr + 1, timestamp_us);
    write_be32(ptr + 9, payload_len);
    
    // Payload
    if (payload && payload_len > 0) {
        memcpy(ptr + MIDWARE_HEADER_SIZE, payload, payload_len);
    }
    
    return needed;
}

int32_t midware_packet_serialize_header(void* buffer,
                                       int32_t buf_capacity,
                                       uint8_t type, 
                                       uint64_t timestamp_us, 
                                       uint32_t payload_len) {
    if (!buffer || buf_capacity < MIDWARE_HEADER_SIZE) return -1;
    
    uint8_t* ptr = (uint8_t*)buffer;
    ptr[0] = type;
    write_be64(ptr + 1, timestamp_us);
    write_be32(ptr + 9, payload_len);
    
    return MIDWARE_HEADER_SIZE;
}

bool midware_packet_parse(const void* raw_data, 
                         int32_t total_len, 
                         midware_packet_header_t* out_header, 
                         const void** out_payload) {
    if (!raw_data || total_len < MIDWARE_HEADER_SIZE || !out_header) {
        return false;
    }

    const uint8_t* ptr = (const uint8_t*)raw_data;

    out_header->type = ptr[0];
    out_header->timestamp_us = read_be64(ptr + 1);
    out_header->payload_len = read_be32(ptr + 9);

    if (out_payload) {
        *out_payload = ptr + MIDWARE_HEADER_SIZE;
    }
    
    // Sanity check
    if (total_len < MIDWARE_HEADER_SIZE + out_header->payload_len) {
        return false; // Truncated packet
    }

    return true;
}

