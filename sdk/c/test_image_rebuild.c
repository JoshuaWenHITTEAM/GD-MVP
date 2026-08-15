#include "midware_image.h"
#include "midware_packet.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void write_slice_index(uint8_t* slice, int index) {
    int encoded = index << 8;
    slice[0] = encoded & 0xFF;
    slice[1] = (encoded >> 8) & 0xFF;
    slice[2] = (encoded >> 16) & 0xFF;
}

static void write_be64(uint8_t* ptr, uint64_t val) {
    ptr[0] = (val >> 56) & 0xFF;
    ptr[1] = (val >> 48) & 0xFF;
    ptr[2] = (val >> 40) & 0xFF;
    ptr[3] = (val >> 32) & 0xFF;
    ptr[4] = (val >> 24) & 0xFF;
    ptr[5] = (val >> 16) & 0xFF;
    ptr[6] = (val >> 8) & 0xFF;
    ptr[7] = val & 0xFF;
}

static void write_be32(uint8_t* ptr, uint32_t val) {
    ptr[0] = (val >> 24) & 0xFF;
    ptr[1] = (val >> 16) & 0xFF;
    ptr[2] = (val >> 8) & 0xFF;
    ptr[3] = val & 0xFF;
}

int main(void) {
    uint8_t* raw = calloc(1, MIDWARE_RDMA_IMAGE_RAW_SIZE);
    uint8_t* image = calloc(1, MIDWARE_RDMA_IMAGE_REBUILT_SIZE);
    uint8_t* image_from_packet = calloc(1, MIDWARE_RDMA_IMAGE_REBUILT_SIZE);
    uint8_t* packet = calloc(1, MIDWARE_HEADER_SIZE + MIDWARE_RDMA_IMAGE_RAW_SIZE);
    if (!raw || !image || !image_from_packet || !packet) {
        fprintf(stderr, "allocation failed\n");
        return 1;
    }

    int base_index = 1000;
    for (int logical = 0; logical < MIDWARE_RDMA_IMAGE_SLICES; logical++) {
        int physical = MIDWARE_RDMA_IMAGE_SLICES - logical - 1;
        uint8_t* slice = raw + (physical * MIDWARE_RDMA_IMAGE_SLICE_SIZE);
        write_slice_index(slice, base_index + logical);
        memset(slice + MIDWARE_RDMA_IMAGE_SLICE_HEADER_SIZE,
               logical & 0xFF,
               MIDWARE_RDMA_IMAGE_SLICE_PAYLOAD_SIZE);
    }

    int32_t written = midware_rebuild_rdma_image(
        raw,
        MIDWARE_RDMA_IMAGE_RAW_SIZE,
        image,
        MIDWARE_RDMA_IMAGE_REBUILT_SIZE);
    if (written != MIDWARE_RDMA_IMAGE_REBUILT_SIZE) {
        fprintf(stderr, "rebuild failed: %d\n", written);
        return 1;
    }

    int samples[] = {0, 1, 255, 1024, MIDWARE_RDMA_IMAGE_SLICES - 1};
    for (size_t i = 0; i < sizeof(samples) / sizeof(samples[0]); i++) {
        int logical = samples[i];
        uint8_t expected = logical & 0xFF;
        int offset = logical * MIDWARE_RDMA_IMAGE_SLICE_PAYLOAD_SIZE;
        if (image[offset] != expected ||
            image[offset + MIDWARE_RDMA_IMAGE_SLICE_PAYLOAD_SIZE - 1] != expected) {
            fprintf(stderr, "unexpected rebuilt byte at logical=%d\n", logical);
            return 1;
        }
    }

    packet[0] = MIDWARE_TYPE_RDMA_IMAGE_RAW;
    write_be64(packet + 1, 123456);
    write_be32(packet + 9, MIDWARE_RDMA_IMAGE_RAW_SIZE);
    memcpy(packet + MIDWARE_HEADER_SIZE, raw, MIDWARE_RDMA_IMAGE_RAW_SIZE);

    written = midware_rebuild_rdma_image_from_packet(
        packet,
        MIDWARE_HEADER_SIZE + MIDWARE_RDMA_IMAGE_RAW_SIZE,
        image_from_packet,
        MIDWARE_RDMA_IMAGE_REBUILT_SIZE);
    if (written != MIDWARE_RDMA_IMAGE_REBUILT_SIZE) {
        fprintf(stderr, "packet rebuild failed: %d\n", written);
        return 1;
    }
    if (memcmp(image, image_from_packet, MIDWARE_RDMA_IMAGE_REBUILT_SIZE) != 0) {
        fprintf(stderr, "packet rebuild output mismatch\n");
        return 1;
    }

    free(raw);
    free(image);
    free(image_from_packet);
    free(packet);
    printf("RDMA image rebuild test passed\n");
    return 0;
}
