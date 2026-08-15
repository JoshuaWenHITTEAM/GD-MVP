#ifndef MIDWARE_SHM_H
#define MIDWARE_SHM_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "midware_packet.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct midware_shm_ctx midware_shm_ctx_t;

/**
 * Batch read entry for high-performance batch reading.
 */
typedef struct {
    const void* data;    // Pointer to data (valid until next read operation)
    int32_t len;         // Length of data
    uint64_t timestamp;  // Parsed timestamp (if parse_headers is true)
    uint8_t type;        // Parsed type (if parse_headers is true)
} midware_shm_batch_entry_t;

/**
 * Deprecated creator/initializer for a SHM writer endpoint.
 *
 * This creates/resizes/reinitializes the SHM file and resets read/write
 * positions. It is retained for middleware-owned SHM initialization and tests
 * only. Application-facing writers should use midware_shm_writer_attach().
 */
midware_shm_ctx_t* midware_shm_producer_init(const char* path, uint64_t capacity);

/**
 * Attach to an existing SHM as a writer without creating or reinitializing it.
 *
 * This function:
 * - opens path with O_RDWR only
 * - does not use O_CREAT
 * - does not ftruncate
 * - does not write the SHM header
 * - does not reset read_pos/write_pos
 * - validates magic/version/ready/format and that stored slot_size is at least
 *   required_capacity
 *
 * @param path Path to an existing middleware-created SHM file
 * @param required_capacity Maximum packet size the caller may write
 * @return Handle to the SHM context, or NULL on failure.
 */
midware_shm_ctx_t* midware_shm_writer_attach(const char* path, uint64_t required_capacity);

/**
 * Initialize a SHM Consumer.
 * Opens an existing SHM file.
 * 
 * @param path Path to the shared memory file
 * @return Handle to the SHM context, or NULL on failure.
 */
midware_shm_ctx_t* midware_shm_consumer_init(const char* path);

/**
 * Write data to the next zero-copy slot.
 * Only valid for Producer.
 * 
 * Note: This writes raw bytes into a slot (no extra framing).
 * 
 * @param ctx Handle
 * @param data Pointer to data
 * @param len Length of data
 * @return true if successful, false if insufficient space.
 */
bool midware_shm_write(midware_shm_ctx_t* ctx, const void* data, int32_t len);

/**
 * Read data from the next zero-copy slot.
 * Only valid for Consumer.
 * 
 * @param ctx Handle
 * @param buf Output buffer
 * @param max_len Capacity of output buffer
 * @return Number of bytes read (positive), 0 if no data, or > max_len if buffer too small.
 */
int32_t midware_shm_read(midware_shm_ctx_t* ctx, void* buf, int32_t max_len);

/**
 * Read the latest data from the zero-copy slots, dropping all older packets.
 * Only valid for Consumer.
 *
 * @param ctx Handle
 * @param buf Output buffer
 * @param max_len Capacity of output buffer
 * @return Number of bytes read (positive), 0 if no data, or > max_len if buffer too small.
 */
int32_t midware_shm_read_latest(midware_shm_ctx_t* ctx, void* buf, int32_t max_len);

/**
 * Peek the latest data from the zero-copy slots without consuming it.
 * Unlike midware_shm_read_latest(), this does not advance the shared read
 * position. The producer may still advance the read position when the queue is
 * full and it needs to drop old entries.
 *
 * @param ctx Handle
 * @param buf Output buffer
 * @param max_len Capacity of output buffer
 * @return Number of bytes read (positive), 0 if no data, or > max_len if buffer too small.
 */
int32_t midware_shm_peek_latest(midware_shm_ctx_t* ctx, void* buf, int32_t max_len);

/**
 * Get the maximum packet size for a single slot.
 */
uint64_t midware_shm_capacity(midware_shm_ctx_t* ctx);

/**
 * Close and unmap the shared memory.
 * Does not delete the file.
 */
void midware_shm_close(midware_shm_ctx_t* ctx);

// --- High Performance APIs (NEW) ---

/**
 * Zero-copy peek: Get a direct pointer to the next available data without copying.
 * MUST call midware_shm_consume() after processing to advance the read position.
 * 
 * WARNING: The returned pointer is only valid until the next read/peek/consume call.
 * Do NOT store the pointer for later use.
 * 
 * @param ctx SHM Consumer Context
 * @param out_data Output pointer to data (direct pointer into SHM, no copy)
 * @param out_len Output length of data
 * @return true if data available, false if empty
 */
bool midware_shm_peek(midware_shm_ctx_t* ctx, const void** out_data, int32_t* out_len);

/**
 * Consume the last peeked entry (advance read position).
 * Call this after midware_shm_peek() to commit the read.
 * 
 * @param ctx SHM Consumer Context
 */
void midware_shm_consume(midware_shm_ctx_t* ctx);

/**
 * Get the number of available entries in the queue without reading.
 * 
 * @param ctx SHM Consumer Context
 * @return Number of available entries (0 to 32)
 */
int32_t midware_shm_available(midware_shm_ctx_t* ctx);

/**
 * Batch read: Read multiple entries at once for maximum throughput.
 * This is the FASTEST way to consume high-frequency data.
 * 
 * The entries array contains direct pointers into SHM (zero-copy).
 * Pointers are valid until the next read operation.
 * 
 * @param ctx SHM Consumer Context
 * @param entries Array to store batch entries
 * @param max_entries Maximum number of entries to read
 * @param parse_headers If true, parse packet headers for timestamp/type
 * @return Number of entries actually read (0 to max_entries)
 */
int32_t midware_shm_read_batch(midware_shm_ctx_t* ctx, midware_shm_batch_entry_t* entries, 
                               int32_t max_entries, bool parse_headers);

/**
 * Non-consuming batch peek: return the latest N entries without advancing the
 * shared read position. Entries are returned oldest-to-newest among the selected
 * recent entries. The entry data pointers are direct pointers into SHM and are
 * valid only until the next SDK operation on this context.
 *
 * @param ctx SHM Consumer Context
 * @param entries Array to store batch entries
 * @param max_entries Maximum number of latest entries to peek
 * @param parse_headers If true, parse packet headers for timestamp/type
 * @return Number of entries actually peeked (0 to max_entries)
 */
int32_t midware_shm_peek_latest_batch(midware_shm_ctx_t* ctx, midware_shm_batch_entry_t* entries,
                                      int32_t max_entries, bool parse_headers);

/**
 * Drain all available entries: Read and discard, returning count.
 * Useful for catching up after falling behind.
 * 
 * @param ctx SHM Consumer Context
 * @return Number of entries drained
 */
int32_t midware_shm_drain(midware_shm_ctx_t* ctx);

// --- High Level Packet Helper APIs ---

/**
 * Convenience: Serialize Packet and Write to SHM in one go.
 * 
 * @param ctx SHM Producer Context
 * @param type Packet Type (0=HighFreq, 1=LowFreq, 2=ImageFrame, 3=RdmaRawImage, 255=ControlCommand)
 * @param timestamp_us Timestamp in microseconds
 * @param payload Pointer to payload data
 * @param payload_len Length of payload
 * @return true if successful
 */
bool midware_shm_write_packet(midware_shm_ctx_t* ctx, uint8_t type, uint64_t timestamp_us, const void* payload, uint32_t payload_len);

/**
 * Convenience: Read from SHM and Parse Packet in one go.
 * 
 * @param ctx SHM Consumer Context
 * @param buf Buffer to read data into
 * @param max_len Capacity of buf
 * @param out_header Output struct for parsed header
 * @param out_payload Output pointer to start of payload within buf (valid only if return > 0)
 * @return 
 *    > 0  : Success (bytes read & parsed)
 *    0    : No data
 *    > max_len : Buffer too small (value is required size). Retry with larger buffer.
 *    -1   : Internal SHM error
 *    -2   : Parse error (data read from SHM but invalid format)
 */
int32_t midware_shm_read_packet(midware_shm_ctx_t* ctx, void* buf, int32_t max_len, midware_packet_header_t* out_header, const void** out_payload);

/**
 * Convenience: Read the latest packet from SHM and Parse Packet in one go.
 * Drops all older packets.
 *
 * @param ctx SHM Consumer Context
 * @param buf Buffer to read data into
 * @param max_len Capacity of buf
 * @param out_header Output struct for parsed header
 * @param out_payload Output pointer to start of payload within buf (valid only if return > 0)
 * @return
 *    > 0  : Success (bytes read & parsed)
 *    0    : No data
 *    > max_len : Buffer too small (value is required size). Retry with larger buffer.
 *    -1   : Internal SHM error
 *    -2   : Parse error (data read from SHM but invalid format)
 */
int32_t midware_shm_read_latest_packet(midware_shm_ctx_t* ctx, void* buf, int32_t max_len, midware_packet_header_t* out_header, const void** out_payload);

/**
 * Convenience: Peek the latest packet from SHM and parse it without consuming it.
 * The shared read position is unchanged.
 *
 * @param ctx SHM Consumer Context
 * @param buf Buffer to read data into
 * @param max_len Capacity of buf
 * @param out_header Output struct for parsed header
 * @param out_payload Output pointer to start of payload within buf (valid only if return > 0)
 * @return
 *    > 0  : Success (bytes read & parsed)
 *    0    : No data
 *    > max_len : Buffer too small (value is required size). Retry with larger buffer.
 *    -1   : Internal SHM error
 *    -2   : Parse error
 */
int32_t midware_shm_peek_latest_packet(midware_shm_ctx_t* ctx, void* buf, int32_t max_len, midware_packet_header_t* out_header, const void** out_payload);

#ifdef __cplusplus
}
#endif

#endif // MIDWARE_SHM_H
