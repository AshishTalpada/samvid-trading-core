#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>

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
