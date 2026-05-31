#include <stdio.h>
#include <fcntl.h>
#include "native_exports.h"
#ifdef _WIN32
#include <io.h>
#define open _open
#define close _close
#define write _write
#else
#include <unistd.h>
#endif

#ifdef __linux__
#include <sys/ioctl.h>
#include <linux/watchdog.h>
#endif

/**
 * Sovereign Heartbeat & Watchdog Controller
 * Monitors the system "Brain" process. If the AI agent hangs for more
 * than 5 seconds, the hardware watchdog will force a cold reboot of 
 * the industrial node to prevent market exposure during a freeze.
 */

int heartbeat_fd = -1;

#ifdef __cplusplus
extern "C" {
#endif

SOVEREIGN_EXPORT int init_hardware_watchdog(const char* device_path) {
    if (device_path == NULL) return -1;  // Invalid parameter
    
#ifdef __linux__
    heartbeat_fd = open(device_path, O_WRONLY);
    if (heartbeat_fd < 0) {
        perror("[HEARTBEAT] Failed to open hardware watchdog");
        return -1;
    }
    
    int timeout = 5; // 5 seconds grace period
    if (ioctl(heartbeat_fd, WDIOC_SETTIMEOUT, &timeout) < 0) {
        perror("[HEARTBEAT] Failed to set watchdog timeout");
        close(heartbeat_fd);
        heartbeat_fd = -1;
        return -1;
    }
    
    printf("[HEARTBEAT] Hardware Watchdog armed (timeout: %d seconds)\n", timeout);
    return 0;
#else
    printf("[HEARTBEAT] Watchdog mock active (Non-Linux platform)\n");
    return 0;
#endif
}

SOVEREIGN_EXPORT void pulse_heartbeat() {
#ifdef __linux__
    if (heartbeat_fd >= 0) {
        int dummy;
        if (ioctl(heartbeat_fd, WDIOC_KEEPALIVE, &dummy) < 0) {
            fprintf(stderr, "[HEARTBEAT] WARNING: Failed to pulse watchdog!\n");
        }
    }
#endif
}

SOVEREIGN_EXPORT void close_heartbeat() {
#ifdef __linux__
    if (heartbeat_fd >= 0) {
        // Magic character 'V' tells the watchdog driver we are closing intentionally
        if (write(heartbeat_fd, "V", 1) < 0) {
            perror("[HEARTBEAT] WARNING: Failed to write magic close character to watchdog");
        }
        close(heartbeat_fd);
        heartbeat_fd = -1;
    }
#endif
}

#ifdef __cplusplus
}
#endif
