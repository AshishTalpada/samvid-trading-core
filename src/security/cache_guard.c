#include <sys/mman.h>
#include <unistd.h>
#include <stdio.h>
#include <errno.h>

/**
 * Memory Poisoning / I-Cache Protection
 * Protects the executable memory pages of the Sovereign Core from 
 * malicious code injection by strictly enforcing W^X (Write XOR Execute).
 * Uses mprotect to lock the instruction cache.
 */

void lock_executable_memory(void* address, size_t len) {
    // Get page size boundary
    long page_size = sysconf(_SC_PAGESIZE);
    void* page_start = (void*)((long)address & ~(page_size - 1));

    // Remove WRITE permissions, keep READ | EXECUTE
    if (mprotect(page_start, len, PROT_READ | PROT_EXEC) == -1) {
        perror("[CACHE GUARD] FATAL: Failed to lock executable memory!");
    } else {
        printf("[CACHE GUARD] Memory region %p locked (W^X enforced).\n", page_start);
    }
}

void trigger_memory_poisoning_alert() {
    printf("[CACHE GUARD] SECURITY BREACH: Unauthorized write attempt to I-Cache!\n");
    // Hard halt
    _exit(99);
}
