#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <signal.h>
#include <string.h>
#include <time.h>

#define SHM_NAME "/sovereign_kill_signal"
#define SHM_SIZE sizeof(int)

// Hardware-level panic trigger. Bypasses Python interpreter entirely.
extern "C" void trigger_flash_crash_kill(const char* reason) {
    printf("[FATAL] HARDWARE KILL SWITCH TRIGGERED: %s\n", reason);
    
    // 1. Broadcast kill signal via POSIX shared memory for other processes
    int shm_fd = shm_open(SHM_NAME, O_CREAT | O_RDWR, 0666);
    if (shm_fd != -1) {
        ftruncate(shm_fd, SHM_SIZE);
        int* kill_flag = (int*)mmap(0, SHM_SIZE, PROT_WRITE, MAP_SHARED, shm_fd, 0);
        if (kill_flag != MAP_FAILED) {
            *kill_flag = 1; 
            msync(kill_flag, SHM_SIZE, MS_SYNC);
            munmap(kill_flag, SHM_SIZE);
        }
        close(shm_fd);
    }

    // 2. Log exact nanosecond timestamp to disk for post-mortem
    FILE* log = fopen("/var/log/sovereign_panic.log", "a");
    if (log) {
        struct timespec ts;
        clock_gettime(CLOCK_REALTIME, &ts);
        fprintf(log, "KILL_TIME: %ld.%09ld | REASON: %s\n", ts.tv_sec, ts.tv_nsec, reason);
        fclose(log);
    }

    // 3. Immediately terminate current process tree to prevent further TCP transmits
    kill(0, SIGKILL); 
    _exit(1);
}
