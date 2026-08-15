/**
 * Test Zero-Copy SHM SDK
 * 
 * This test verifies the slot-based zero-copy SHM implementation.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <time.h>
#include "midware_shm.h"
#include "midware_packet.h"

#define TEST_SHM_PATH "/dev/shm/test-sdk-zerocopy"
#define SLOT_SIZE 4096  // 4KB per slot
#define NUM_PACKETS 100

static uint64_t get_timestamp_us() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000 + ts.tv_nsec / 1000;
}

void run_producer() {
    printf("[Producer] Starting...\n");
    
    midware_shm_ctx_t* owner = midware_shm_producer_init(TEST_SHM_PATH, SLOT_SIZE);
    if (!owner) {
        fprintf(stderr, "[Producer] Failed to init SHM\n");
        exit(1);
    }
    midware_shm_close(owner);

    midware_shm_ctx_t* ctx = midware_shm_writer_attach(TEST_SHM_PATH, SLOT_SIZE);
    if (!ctx) {
        fprintf(stderr, "[Producer] Failed to attach SHM writer\n");
        exit(1);
    }
    
    printf("[Producer] SHM initialized, slot_size=%lu\n", midware_shm_capacity(ctx));
    
    // Send packets
    for (int i = 0; i < NUM_PACKETS; i++) {
        char payload[64];
        snprintf(payload, sizeof(payload), "Packet #%d from SDK", i);
        uint32_t payload_len = strlen(payload);
        
        uint64_t ts = get_timestamp_us();
        
        if (midware_shm_write_packet(ctx, 0, ts, payload, payload_len)) {
            printf("[Producer] Sent packet %d, ts=%lu\n", i, ts);
        } else {
            fprintf(stderr, "[Producer] Failed to send packet %d\n", i);
        }
        
        usleep(10000); // 10ms between packets
    }
    
    printf("[Producer] Done, sent %d packets\n", NUM_PACKETS);
    midware_shm_close(ctx);
}

void run_consumer() {
    printf("[Consumer] Starting...\n");
    
    // Wait for producer to create SHM
    for (int i = 0; i < 50; i++) {
        if (access(TEST_SHM_PATH, F_OK) == 0) break;
        usleep(100000); // 100ms
    }
    
    midware_shm_ctx_t* ctx = midware_shm_consumer_init(TEST_SHM_PATH);
    if (!ctx) {
        fprintf(stderr, "[Consumer] Failed to init SHM\n");
        exit(1);
    }
    
    printf("[Consumer] SHM connected, slot_size=%lu\n", midware_shm_capacity(ctx));
    
    int received = 0;
    int empty_polls = 0;
    uint8_t buffer[SLOT_SIZE];
    midware_packet_header_t header;
    const void* payload_ptr;
    
    while (received < NUM_PACKETS && empty_polls < 100) {
        int32_t len = midware_shm_read_packet(ctx, buffer, sizeof(buffer), &header, &payload_ptr);
        
        if (len > 0) {
            empty_polls = 0;
            received++;
            
            // Print payload as string
            char payload_str[256];
            int copy_len = header.payload_len < 255 ? header.payload_len : 255;
            memcpy(payload_str, payload_ptr, copy_len);
            payload_str[copy_len] = '\0';
            
            printf("[Consumer] Recv #%d: type=%d, ts=%lu, payload='%s'\n",
                   received, header.type, header.timestamp_us, payload_str);
        } else if (len == 0) {
            empty_polls++;
            usleep(10000); // 10ms
        } else {
            fprintf(stderr, "[Consumer] Error: %d\n", len);
            break;
        }
    }
    
    printf("[Consumer] Done, received %d packets\n", received);
    midware_shm_close(ctx);
    
    // Cleanup
    unlink(TEST_SHM_PATH);
}

int main(int argc, char** argv) {
    printf("=== Zero-Copy SHM SDK Test ===\n");
    
    // Remove old SHM file
    unlink(TEST_SHM_PATH);
    
    pid_t pid = fork();
    if (pid < 0) {
        perror("fork failed");
        return 1;
    } else if (pid == 0) {
        // Child: Consumer
        sleep(1); // Wait for producer to start
        run_consumer();
        exit(0);
    } else {
        // Parent: Producer
        run_producer();
        
        // Wait for consumer
        int status;
        waitpid(pid, &status, 0);
        
        if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
            printf("\n=== TEST PASSED ===\n");
            return 0;
        } else {
            printf("\n=== TEST FAILED ===\n");
            return 1;
        }
    }
}
