/**
 * Zero-Copy Shared Memory SDK Implementation (compatible with Java V2)
 *
 * This SDK must match `app/src/main/java/org/example/shm/ZeroCopySharedMemory.java`.
 * Important: shared-memory metadata is stored as 64-bit BIG-ENDIAN values.
 *
 * Memory Layout (V2, cache-line aligned):
 *   [0..63]    Producer cache line
 *     - [0..7]   WRITE_POS (u64 BE)
 *     - [8..15]  CACHED_READ_POS (u64 BE)
 *     - [16..23] OVERWRITE_COUNT (u64 BE)
 *     - [24..31] NEXT_SLOT (u64 BE)
 *   [64..127]  Consumer cache line
 *     - [64..71] READ_POS (u64 BE)
 *     - [72..79] CACHED_WRITE_POS (u64 BE)
 *     - [80..87] CONSUME_COUNT (u64 BE)
 *   [128..191] Config cache line
 *     - [128..135] MAGIC "SHMMIDW2" (u64 BE)
 *     - [136..143] VERSION=2 (u64 BE)
 *     - [144..151] FORMAT_READY (u64 BE) = (format<<32 | ready)
 *     - [152..159] SLOT_COUNT (u64 BE)
 *     - [160..167] SLOT_SIZE (u64 BE)
 *   [256..2303] Index queue entries (256 * 8B = 2048 bytes, u64 BE)
 *     - encoded = (slotIndex<<32 | actualLength)
 *   [2304..]    Slots data
 */

#include "midware_shm.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <errno.h>
#include <endian.h>

// Layout constants (must match Java ZeroCopySharedMemory)
#define CACHE_LINE              64

// Cache line 0 (producer)
#define WRITE_POS_OFFSET        0
#define CACHED_READ_POS_OFFSET  8
#define OVERWRITE_COUNT_OFFSET  16
#define NEXT_SLOT_OFFSET        24

// Cache line 1 (consumer)
#define READ_POS_OFFSET         CACHE_LINE

// Cache line 2 (config)
#define CONFIG_OFFSET           (2 * CACHE_LINE)   // 128
#define MAGIC_OFFSET            (CONFIG_OFFSET)
#define VERSION_OFFSET          (CONFIG_OFFSET + 8)
#define FORMAT_READY_OFFSET     (CONFIG_OFFSET + 16)
#define SLOT_COUNT_OFFSET       (CONFIG_OFFSET + 24)
#define SLOT_SIZE_OFFSET        (CONFIG_OFFSET + 32)

// Index queue + slots
#define QUEUE_OFFSET            (4 * CACHE_LINE)   // 256
#define INDEX_QUEUE_SIZE        256  // Increased from 32 for high-freq data
#define INDEX_QUEUE_MASK        (INDEX_QUEUE_SIZE - 1)
#define SLOTS_OFFSET            (QUEUE_OFFSET + INDEX_QUEUE_SIZE * 8)  // 256 + 256*8 = 2304

// Magic/version/format
#define SHM_MAGIC               0x53484D4D49445732ULL  // "SHMMIDW2"
#define SHM_VERSION             2ULL
#define FORMAT_ZEROCOPY_V2      3U
#define READY_YES               1U

// Special value for empty slot
#define EMPTY_SLOT          ((uint64_t)-1)

struct midware_shm_ctx {
    int fd;
    uint8_t* map_base;
    uint64_t map_size;
    uint64_t slot_count;
    uint64_t slot_size;
    bool is_producer;
    
    // Pointers to shared fields (stored as BE u64)
    volatile uint64_t* p_write_pos;
    volatile uint64_t* p_read_pos;
    volatile uint64_t* p_magic;
    volatile uint64_t* p_version;
    volatile uint64_t* p_format_ready;
    volatile uint64_t* p_slot_count;
    volatile uint64_t* p_slot_size;
    volatile uint64_t* index_queue;
    uint8_t* slots_area;
    
    // Producer: next slot to allocate (round-robin)
    int next_free_slot;
};

// Memory barrier
static inline void memory_barrier() {
    __sync_synchronize();
}

static inline uint64_t read_u64_be(volatile uint64_t* addr) {
    uint64_t v = *addr;
    return be64toh(v);
}

static inline void write_u64_be(volatile uint64_t* addr, uint64_t val) {
    *addr = htobe64(val);
}

static inline uint64_t read_u64_be_bytes(const uint8_t* p) {
    uint64_t v;
    memcpy(&v, p, sizeof(v));
    return be64toh(v);
}

static inline uint64_t pack_format_ready(uint32_t format, uint32_t ready) {
    return ((uint64_t)format << 32) | (uint64_t)ready;
}

midware_shm_ctx_t* midware_shm_producer_init(const char* path, uint64_t capacity) {
    // For zero-copy mode, capacity is interpreted as slot_size
    // Default slot count = 32 (matches INDEX_QUEUE_SIZE)
    const uint64_t slot_count = INDEX_QUEUE_SIZE;
    uint64_t slot_size = capacity; // User provides slot size
    
    if (slot_size <= 0) return NULL;

    midware_shm_ctx_t* ctx = (midware_shm_ctx_t*)calloc(1, sizeof(midware_shm_ctx_t));
    if (!ctx) return NULL;

    ctx->is_producer = true;
    ctx->slot_count = slot_count;
    ctx->slot_size = slot_size;
    ctx->next_free_slot = 0;

    // Match Java behavior: producer deletes existing file to avoid format mismatch.
    unlink(path);

    ctx->fd = open(path, O_RDWR | O_CREAT, 0666);
    if (ctx->fd < 0) {
        perror("shm open failed");
        free(ctx);
        return NULL;
    }

    uint64_t total_size = SLOTS_OFFSET + slot_count * slot_size;
    if (ftruncate(ctx->fd, total_size) < 0) {
        perror("ftruncate failed");
        close(ctx->fd);
        free(ctx);
        return NULL;
    }

    ctx->map_base = (uint8_t*)mmap(NULL, total_size, PROT_READ | PROT_WRITE, MAP_SHARED, ctx->fd, 0);
    if (ctx->map_base == MAP_FAILED) {
        perror("mmap failed");
        close(ctx->fd);
        free(ctx);
        return NULL;
    }

    ctx->map_size = total_size;
    
    // Setup pointers
    ctx->p_write_pos = (volatile uint64_t*)(ctx->map_base + WRITE_POS_OFFSET);
    ctx->p_read_pos = (volatile uint64_t*)(ctx->map_base + READ_POS_OFFSET);
    ctx->p_magic = (volatile uint64_t*)(ctx->map_base + MAGIC_OFFSET);
    ctx->p_version = (volatile uint64_t*)(ctx->map_base + VERSION_OFFSET);
    ctx->p_format_ready = (volatile uint64_t*)(ctx->map_base + FORMAT_READY_OFFSET);
    ctx->p_slot_count = (volatile uint64_t*)(ctx->map_base + SLOT_COUNT_OFFSET);
    ctx->p_slot_size = (volatile uint64_t*)(ctx->map_base + SLOT_SIZE_OFFSET);
    ctx->index_queue = (volatile uint64_t*)(ctx->map_base + QUEUE_OFFSET);
    ctx->slots_area = ctx->map_base + SLOTS_OFFSET;

    // Initialize SHM (V2)
    // 1) Not ready yet
    write_u64_be(ctx->p_magic, SHM_MAGIC);
    write_u64_be(ctx->p_version, SHM_VERSION);
    write_u64_be(ctx->p_format_ready, pack_format_ready(FORMAT_ZEROCOPY_V2, 0));
    write_u64_be(ctx->p_slot_count, slot_count);
    write_u64_be(ctx->p_slot_size, slot_size);

    // 2) Positions
    write_u64_be(ctx->p_write_pos, 0);
    write_u64_be(ctx->p_read_pos, 0);

    // 3) Clear index queue
    for (int i = 0; i < INDEX_QUEUE_SIZE; i++) {
        write_u64_be(&ctx->index_queue[i], EMPTY_SLOT);
    }

    memory_barrier();

    // 4) Mark ready
    write_u64_be(ctx->p_format_ready, pack_format_ready(FORMAT_ZEROCOPY_V2, READY_YES));
    memory_barrier();

    return ctx;
}

midware_shm_ctx_t* midware_shm_consumer_init(const char* path) {
    midware_shm_ctx_t* ctx = (midware_shm_ctx_t*)calloc(1, sizeof(midware_shm_ctx_t));
    if (!ctx) return NULL;

    ctx->is_producer = false;
    ctx->fd = open(path, O_RDWR, 0666);
    if (ctx->fd < 0) {
        free(ctx);
        return NULL;
    }

    // Wait for producer ready (up to 30s)
    const int64_t max_wait_ms = 30000;
    int64_t waited = 0;
    uint8_t header[SLOTS_OFFSET];

    while (waited < max_wait_ms) {
        ssize_t n = pread(ctx->fd, header, SLOTS_OFFSET, 0);
        if (n < SLOTS_OFFSET) {
            usleep(50 * 1000);
            waited += 50;
            continue;
        }

        uint64_t magic = read_u64_be_bytes(header + MAGIC_OFFSET);
        uint64_t format_ready = read_u64_be_bytes(header + FORMAT_READY_OFFSET);
        uint32_t ready = (uint32_t)(format_ready & 0xFFFFFFFFu);
        uint32_t format = (uint32_t)(format_ready >> 32);

        if (magic == SHM_MAGIC && ready == READY_YES && format == FORMAT_ZEROCOPY_V2) {
            ctx->slot_count = read_u64_be_bytes(header + SLOT_COUNT_OFFSET);
            ctx->slot_size = read_u64_be_bytes(header + SLOT_SIZE_OFFSET);
            break;
        }

        usleep(50 * 1000);
        waited += 50;
    }

    if (ctx->slot_count == 0 || ctx->slot_size == 0) {
        close(ctx->fd);
        free(ctx);
        return NULL;
    }

    // Map the whole file size (producer might round/allocate slightly differently)
    struct stat st;
    if (fstat(ctx->fd, &st) != 0) {
        close(ctx->fd);
        free(ctx);
        return NULL;
    }
    uint64_t total_size = (uint64_t)st.st_size;

    ctx->map_base = (uint8_t*)mmap(NULL, total_size, PROT_READ | PROT_WRITE, MAP_SHARED, ctx->fd, 0);
    if (ctx->map_base == MAP_FAILED) {
        close(ctx->fd);
        free(ctx);
        return NULL;
    }

    ctx->map_size = total_size;

    // Setup pointers
    ctx->p_write_pos = (volatile uint64_t*)(ctx->map_base + WRITE_POS_OFFSET);
    ctx->p_read_pos = (volatile uint64_t*)(ctx->map_base + READ_POS_OFFSET);
    ctx->p_magic = (volatile uint64_t*)(ctx->map_base + MAGIC_OFFSET);
    ctx->p_version = (volatile uint64_t*)(ctx->map_base + VERSION_OFFSET);
    ctx->p_format_ready = (volatile uint64_t*)(ctx->map_base + FORMAT_READY_OFFSET);
    ctx->p_slot_count = (volatile uint64_t*)(ctx->map_base + SLOT_COUNT_OFFSET);
    ctx->p_slot_size = (volatile uint64_t*)(ctx->map_base + SLOT_SIZE_OFFSET);
    ctx->index_queue = (volatile uint64_t*)(ctx->map_base + QUEUE_OFFSET);
    ctx->slots_area = ctx->map_base + SLOTS_OFFSET;

    return ctx;
}

bool midware_shm_write(midware_shm_ctx_t* ctx, const void* data, int32_t len) {
    if (!ctx || !ctx->is_producer || len < 0) return false;
    if ((uint64_t)len > ctx->slot_size) return false;

    uint64_t head = read_u64_be(ctx->p_write_pos);
    uint64_t tail = read_u64_be(ctx->p_read_pos);

    // Queue full -> overwrite oldest (match Java behavior)
    if (head - tail >= INDEX_QUEUE_SIZE) {
        uint64_t new_tail = head - INDEX_QUEUE_SIZE + 1;
        write_u64_be(ctx->p_read_pos, new_tail);
        tail = new_tail;
    }

    // Allocate slot (round-robin)
    int slot_index = ctx->next_free_slot;
    ctx->next_free_slot = (ctx->next_free_slot + 1) % ctx->slot_count;

    // Copy data to slot
    uint8_t* slot_ptr = ctx->slots_area + slot_index * ctx->slot_size;
    memcpy(slot_ptr, data, len);

    memory_barrier();

    // Encode: [slot_index (32 bits) | actual_length (32 bits)]
    uint64_t encoded = ((uint64_t)slot_index << 32) | ((uint32_t)len);

    // Write to index queue
    int queue_index = (int)(head & INDEX_QUEUE_MASK);
    write_u64_be(&ctx->index_queue[queue_index], encoded);

    memory_barrier();

    // Update head (commit)
    write_u64_be(ctx->p_write_pos, head + 1);

    return true;
}

int32_t midware_shm_read(midware_shm_ctx_t* ctx, void* buf, int32_t max_len) {
    if (!ctx || ctx->is_producer) return -1;

    uint64_t head = read_u64_be(ctx->p_write_pos);
    uint64_t tail = read_u64_be(ctx->p_read_pos);

    if (tail >= head) {
        return 0; // Empty
    }

    int queue_index = (int)(tail & INDEX_QUEUE_MASK);
    uint64_t encoded = read_u64_be(&ctx->index_queue[queue_index]);

    if (encoded == EMPTY_SLOT) {
        return 0;
    }

    int slot_index = (int)(encoded >> 32);
    int32_t actual_len = (int32_t)(encoded & 0xFFFFFFFF);

    if (slot_index < 0 || (uint64_t)slot_index >= ctx->slot_count) {
        return -1;
    }
    if (actual_len < 0 || (uint64_t)actual_len > ctx->slot_size) {
        return -1;
    }

    // Check buffer size
    if (buf == NULL || actual_len > max_len) {
        return actual_len; // Return required size
    }

    // Copy data from slot
    uint8_t* slot_ptr = ctx->slots_area + slot_index * ctx->slot_size;
    memcpy(buf, slot_ptr, actual_len);

    memory_barrier();

    // Update tail (commit read)
    write_u64_be(ctx->p_read_pos, tail + 1);

    return actual_len;
}

int32_t midware_shm_read_latest(midware_shm_ctx_t* ctx, void* buf, int32_t max_len) {
    if (!ctx || ctx->is_producer) return -1;

    uint64_t head = read_u64_be(ctx->p_write_pos);
    uint64_t tail = read_u64_be(ctx->p_read_pos);

    if (tail >= head) {
        return 0; // Empty
    }

    // Skip to latest entry
    uint64_t latest_tail = head - 1;
    
    int queue_index = (int)(latest_tail & INDEX_QUEUE_MASK);
    uint64_t encoded = read_u64_be(&ctx->index_queue[queue_index]);

    if (encoded == EMPTY_SLOT) {
        return 0;
    }

    int slot_index = (int)(encoded >> 32);
    int32_t actual_len = (int32_t)(encoded & 0xFFFFFFFF);

    if (slot_index < 0 || (uint64_t)slot_index >= ctx->slot_count) {
        return -1;
    }
    if (actual_len < 0 || (uint64_t)actual_len > ctx->slot_size) {
        return -1;
    }

    // Check buffer size
    if (buf == NULL || actual_len > max_len) {
        // Advance tail to drop older packets
        write_u64_be(ctx->p_read_pos, latest_tail);
        return actual_len;
    }

    // Copy data from slot
    uint8_t* slot_ptr = ctx->slots_area + slot_index * ctx->slot_size;
    memcpy(buf, slot_ptr, actual_len);

    memory_barrier();

    // Update tail to consume all including latest
    write_u64_be(ctx->p_read_pos, latest_tail + 1);

    return actual_len;
}

uint64_t midware_shm_capacity(midware_shm_ctx_t* ctx) {
    return ctx ? ctx->slot_size : 0;
}

void midware_shm_close(midware_shm_ctx_t* ctx) {
    if (!ctx) return;
    if (ctx->map_base && ctx->map_base != MAP_FAILED) {
        munmap(ctx->map_base, ctx->map_size);
    }
    if (ctx->fd >= 0) {
        close(ctx->fd);
    }
    free(ctx);
}

// ============================================================================
// High Performance APIs
// ============================================================================

// Lightweight read barrier (cheaper than full barrier on x86)
#if defined(__x86_64__) || defined(__i386__)
#define read_barrier() __asm__ __volatile__("lfence" ::: "memory")
#define write_barrier() __asm__ __volatile__("sfence" ::: "memory")
#else
#define read_barrier() __sync_synchronize()
#define write_barrier() __sync_synchronize()
#endif

// Prefetch for read
#define prefetch_read(addr) __builtin_prefetch((addr), 0, 3)

int32_t midware_shm_available(midware_shm_ctx_t* ctx) {
    if (!ctx || ctx->is_producer) return 0;
    
    uint64_t head = read_u64_be(ctx->p_write_pos);
    uint64_t tail = read_u64_be(ctx->p_read_pos);
    
    if (tail >= head) return 0;
    
    uint64_t avail = head - tail;
    if (avail > INDEX_QUEUE_SIZE) avail = INDEX_QUEUE_SIZE;
    
    return (int32_t)avail;
}

bool midware_shm_peek(midware_shm_ctx_t* ctx, const void** out_data, int32_t* out_len) {
    if (!ctx || ctx->is_producer || !out_data || !out_len) return false;

    uint64_t head = read_u64_be(ctx->p_write_pos);
    uint64_t tail = read_u64_be(ctx->p_read_pos);

    if (tail >= head) {
        return false; // Empty
    }

    int queue_index = (int)(tail & INDEX_QUEUE_MASK);
    uint64_t encoded = read_u64_be(&ctx->index_queue[queue_index]);

    if (encoded == EMPTY_SLOT) {
        return false;
    }

    int slot_index = (int)(encoded >> 32);
    int32_t actual_len = (int32_t)(encoded & 0xFFFFFFFF);

    if (slot_index < 0 || (uint64_t)slot_index >= ctx->slot_count) {
        return false;
    }
    if (actual_len < 0 || (uint64_t)actual_len > ctx->slot_size) {
        return false;
    }

    read_barrier();

    // Return direct pointer (zero-copy)
    *out_data = ctx->slots_area + slot_index * ctx->slot_size;
    *out_len = actual_len;

    return true;
}

void midware_shm_consume(midware_shm_ctx_t* ctx) {
    if (!ctx || ctx->is_producer) return;
    
    uint64_t tail = read_u64_be(ctx->p_read_pos);
    write_u64_be(ctx->p_read_pos, tail + 1);
}

int32_t midware_shm_read_batch(midware_shm_ctx_t* ctx, midware_shm_batch_entry_t* entries, 
                               int32_t max_entries, bool parse_headers) {
    if (!ctx || ctx->is_producer || !entries || max_entries <= 0) return 0;

    uint64_t head = read_u64_be(ctx->p_write_pos);
    uint64_t tail = read_u64_be(ctx->p_read_pos);

    if (tail >= head) {
        return 0; // Empty
    }

    // Calculate how many entries we can read
    uint64_t available = head - tail;
    if (available > (uint64_t)max_entries) available = (uint64_t)max_entries;
    if (available > INDEX_QUEUE_SIZE) available = INDEX_QUEUE_SIZE;

    int32_t count = 0;

    for (uint64_t i = 0; i < available; i++) {
        uint64_t pos = tail + i;
        int queue_index = (int)(pos & INDEX_QUEUE_MASK);
        
        // Prefetch next queue entry
        if (i + 1 < available) {
            int next_idx = (int)((pos + 1) & INDEX_QUEUE_MASK);
            prefetch_read(&ctx->index_queue[next_idx]);
        }
        
        uint64_t encoded = read_u64_be(&ctx->index_queue[queue_index]);

        if (encoded == EMPTY_SLOT) {
            break;
        }

        int slot_index = (int)(encoded >> 32);
        int32_t actual_len = (int32_t)(encoded & 0xFFFFFFFF);

        if (slot_index < 0 || (uint64_t)slot_index >= ctx->slot_count) {
            break;
        }
        if (actual_len < 0 || (uint64_t)actual_len > ctx->slot_size) {
            break;
        }

        // Get pointer to slot data
        const uint8_t* slot_ptr = ctx->slots_area + slot_index * ctx->slot_size;
        
        // Prefetch slot data
        prefetch_read(slot_ptr);
        
        entries[count].data = slot_ptr;
        entries[count].len = actual_len;
        entries[count].timestamp = 0;
        entries[count].type = 0;

        // Optionally parse header
        if (parse_headers && actual_len >= 13) {
            midware_packet_header_t hdr;
            const void* payload;
            if (midware_packet_parse(slot_ptr, actual_len, &hdr, &payload)) {
                entries[count].timestamp = hdr.timestamp_us;
                entries[count].type = hdr.type;
            }
        }

        count++;
    }

    read_barrier();

    // Commit all reads at once
    if (count > 0) {
        write_u64_be(ctx->p_read_pos, tail + count);
    }

    return count;
}

int32_t midware_shm_drain(midware_shm_ctx_t* ctx) {
    if (!ctx || ctx->is_producer) return 0;

    uint64_t head = read_u64_be(ctx->p_write_pos);
    uint64_t tail = read_u64_be(ctx->p_read_pos);

    if (tail >= head) {
        return 0;
    }

    uint64_t drained = head - tail;
    if (drained > INDEX_QUEUE_SIZE) drained = INDEX_QUEUE_SIZE;

    // Advance to head (drop all)
    write_u64_be(ctx->p_read_pos, head);

    return (int32_t)drained;
}

// --- High Level Packet Helper APIs ---

bool midware_shm_write_packet(midware_shm_ctx_t* ctx, uint8_t type, uint64_t timestamp_us, const void* payload, uint32_t payload_len) {
    if (!ctx || !payload) return false;

    uint32_t total_size = midware_packet_size(payload_len);
    
    // Stack optimization for small packets
    uint8_t stack_buf[4096];
    uint8_t* buf = stack_buf;
    bool needs_free = false;

    if (total_size > sizeof(stack_buf)) {
        buf = (uint8_t*)malloc(total_size);
        if (!buf) return false;
        needs_free = true;
    }

    // Serialize packet
    int serialized_len = midware_packet_serialize(buf, total_size, type, timestamp_us, payload, payload_len);
    if (serialized_len <= 0) {
        if (needs_free) free(buf);
        return false;
    }

    // Write to SHM
    bool res = midware_shm_write(ctx, buf, serialized_len);

    if (needs_free) free(buf);
    return res;
}

int32_t midware_shm_read_packet(midware_shm_ctx_t* ctx, void* buf, int32_t max_len, midware_packet_header_t* out_header, const void** out_payload) {
    int32_t len = midware_shm_read(ctx, buf, max_len);
    
    if (len <= 0) return len;
    if (len > max_len) return len; // Buffer too small

    if (midware_packet_parse(buf, len, out_header, out_payload)) {
        return len;
    } else {
        return -2; // Parse failed
    }
}

int32_t midware_shm_read_latest_packet(midware_shm_ctx_t* ctx, void* buf, int32_t max_len, midware_packet_header_t* out_header, const void** out_payload) {
    int32_t len = midware_shm_read_latest(ctx, buf, max_len);

    if (len <= 0) return len;
    if (len > max_len) return len;

    if (midware_packet_parse(buf, len, out_header, out_payload)) {
        return len;
    } else {
        return -2;
    }
}
