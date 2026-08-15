#include "midware_image.h"
#include "midware_packet.h"

#include <stdbool.h>
#include <string.h>

static inline int slice_index(const uint8_t* slice) {
    int b0 = slice[0] & 0xFF;
    int b1 = slice[1] & 0xFF;
    int b2 = slice[2] & 0xFF;
    return (b0 | (b1 << 8) | (b2 << 16)) >> 8;
}

int32_t midware_rebuild_rdma_image(const void* raw_slices,
                                   uint32_t raw_len,
                                   void* out_image,
                                   uint32_t out_capacity) {
    if (!raw_slices || !out_image) {
        return -1;
    }
    if (raw_len != MIDWARE_RDMA_IMAGE_RAW_SIZE) {
        return -2;
    }
    if (out_capacity < MIDWARE_RDMA_IMAGE_REBUILT_SIZE) {
        return -3;
    }

    const uint8_t* raw = (const uint8_t*)raw_slices;
    uint8_t* out = (uint8_t*)out_image;
    int min_index = INT32_MAX;
    int indices[MIDWARE_RDMA_IMAGE_SLICES];

    for (int i = 0; i < MIDWARE_RDMA_IMAGE_SLICES; i++) {
        const uint8_t* slice = raw + (i * MIDWARE_RDMA_IMAGE_SLICE_SIZE);
        int index = slice_index(slice);
        indices[i] = index;
        if (index < min_index) {
            min_index = index;
        }
    }

    memset(out, 0, MIDWARE_RDMA_IMAGE_REBUILT_SIZE);

    for (int i = 0; i < MIDWARE_RDMA_IMAGE_SLICES; i++) {
        int normalized = indices[i] - min_index;
        if (normalized < 0 || normalized >= MIDWARE_RDMA_IMAGE_SLICES) {
            continue;
        }

        const uint8_t* src = raw
            + (i * MIDWARE_RDMA_IMAGE_SLICE_SIZE)
            + MIDWARE_RDMA_IMAGE_SLICE_HEADER_SIZE;
        uint8_t* dst = out + (normalized * MIDWARE_RDMA_IMAGE_SLICE_PAYLOAD_SIZE);
        memcpy(dst, src, MIDWARE_RDMA_IMAGE_SLICE_PAYLOAD_SIZE);
    }

    return MIDWARE_RDMA_IMAGE_REBUILT_SIZE;
}

int32_t midware_rebuild_rdma_image_from_packet(const void* packet,
                                               uint32_t packet_len,
                                               void* out_image,
                                               uint32_t out_capacity) {
    if (!packet || !out_image) {
        return -1;
    }

    midware_packet_header_t header;
    const void* payload = NULL;
    if (!midware_packet_parse(packet, (int32_t)packet_len, &header, &payload)) {
        return -2;
    }
    if (header.type != MIDWARE_TYPE_RDMA_IMAGE_RAW) {
        return -4;
    }
    if (header.payload_len != MIDWARE_RDMA_IMAGE_RAW_SIZE) {
        return -2;
    }

    int32_t res = midware_rebuild_rdma_image(
        payload,
        header.payload_len,
        out_image,
        out_capacity);
    if (res == -2) {
        return -2;
    }
    return res;
}
