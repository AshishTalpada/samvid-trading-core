#include <stdio.h>
#include <errno.h>

#ifdef _WIN32
#include <windows.h>
#include <process.h>
// Windows compatibility for POSIX memory protection
#define PROT_READ 0x1
#define PROT_EXEC 0x4
#define _SC_PAGESIZE 0
static inline long sysconf(int name) {
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    return (long)si.dwPageSize;
}
static inline int mprotect(void* addr, size_t len, int prot) {
    DWORD old;
    return VirtualProtect(addr, len, PAGE_EXECUTE_READ, &old) ? 0 : -1;
}
#define _exit exit
#else
#include <sys/mman.h>
#include <unistd.h>
#endif

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
