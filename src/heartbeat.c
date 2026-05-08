#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <linux/watchdog.h>

int main() {
    int fd = open("/dev/watchdog", O_WRONLY);
    while(1) {
        ioctl(fd, WDIOC_KEEPALIVE, 0);
        usleep(500000); // 500ms
    }
    return 0;
}
