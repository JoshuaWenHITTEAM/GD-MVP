#ifndef MIDWARE_IMAGE_H
#define MIDWARE_IMAGE_H

#include <stdint.h>
#include "midware_packet.h"

#ifdef __cplusplus
extern "C" {
#endif

#define MIDWARE_RDMA_IMAGE_SLICES 4096
#define MIDWARE_RDMA_IMAGE_SLICE_SIZE 264
#define MIDWARE_RDMA_IMAGE_SLICE_HEADER_SIZE 8
#define MIDWARE_RDMA_IMAGE_SLICE_PAYLOAD_SIZE 256
#define MIDWARE_RDMA_IMAGE_RAW_SIZE (MIDWARE_RDMA_IMAGE_SLICES * MIDWARE_RDMA_IMAGE_SLICE_SIZE)
#define MIDWARE_RDMA_IMAGE_REBUILT_SIZE (MIDWARE_RDMA_IMAGE_SLICES * MIDWARE_RDMA_IMAGE_SLICE_PAYLOAD_SIZE)

/**
 * Rebuild a raw RDMA image slice payload into pure image bytes.
 *
 * Input layout:
 *   4096 slices, each 264 bytes:
 *     [0..7]   slice header
 *     [8..263] image payload
 *
 * Output layout:
 *   4096 reordered payload chunks, each 256 bytes.
 *
 * @return bytes written (MIDWARE_RDMA_IMAGE_REBUILT_SIZE), or a negative error:
 *   -1 invalid argument
 *   -2 raw_len is not MIDWARE_RDMA_IMAGE_RAW_SIZE
 *   -3 out_capacity is too small
 */
int32_t midware_rebuild_rdma_image(const void* raw_slices,
                                   uint32_t raw_len,
                                   void* out_image,
                                   uint32_t out_capacity);

/**
 * Parse a type=3 middleware packet and rebuild its payload into pure image bytes.
 *
 * @return bytes written (MIDWARE_RDMA_IMAGE_REBUILT_SIZE), or a negative error:
 *   -1 invalid argument
 *   -2 packet parse failed or payload length is invalid
 *   -3 out_capacity is too small
 *   -4 packet type is not MIDWARE_TYPE_RDMA_IMAGE_RAW
 */
int32_t midware_rebuild_rdma_image_from_packet(const void* packet,
                                               uint32_t packet_len,
                                               void* out_image,
                                               uint32_t out_capacity);

#ifdef __cplusplus
}
#endif

#endif // MIDWARE_IMAGE_H
