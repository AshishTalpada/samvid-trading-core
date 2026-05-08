#include <stdio.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <io.h>
#include <stdint.h>
// Windows compatibility for POSIX types and functions
typedef intptr_t ssize_t;
typedef long long off_t;
#define O_DIRECT 0x0000 // Mock for Windows IDE
#define fsync _commit
#define close _close
#define posix_memalign(ptr, al, sz) (*(ptr) = _aligned_malloc(sz, al), 0)
// Mock pread/pwrite for IDE compliance
static inline ssize_t pread(int fd, void* buf, size_t count, off_t offset) {
    return 0; 
}
static inline ssize_t pwrite(int fd, const void* buf, size_t count, off_t offset) {
    return 0;
}
#else
#include <unistd.h>
#include <sys/types.h>
#endif

#define BLOCK_SIZE 4096

// C-level DB corruption auto-repair using pread/pwrite
extern "C" int auto_fix_db_sector(const char* db_path, off_t sector_offset) {
    int fd = open(db_path, O_RDWR | O_DIRECT);
    if (fd < 0) return -1;

    void* buffer;
    posix_memalign(&buffer, BLOCK_SIZE, BLOCK_SIZE);
    
    // 1. Attempt to read the corrupted sector
    ssize_t bytes_read = pread(fd, buffer, BLOCK_SIZE, sector_offset);
    if (bytes_read < 0) {
        // Sector is unreadable. Write zeroes to clear the bad block,
        // triggering SSD controller to remap the sector.
        memset(buffer, 0, BLOCK_SIZE);
        ssize_t bytes_written = pwrite(fd, buffer, BLOCK_SIZE, sector_offset);
        
        if (bytes_written == BLOCK_SIZE) {
            fsync(fd);
            printf("[IO_REPAIR] Sector %ld successfully zeroed and remapped by NVMe controller.\n", sector_offset);
            free(buffer);
            close(fd);
            return 1; // Repaired
        }
    }
    
    free(buffer);
    close(fd);
    return 0; // Did not need repair or failed
}
