#include <unistd.h>

extern "C" void trigger_flash_crash_kill() {
    // Hardware trigger to liquidate in <10ms if drop detected
    _exit(1);
}
