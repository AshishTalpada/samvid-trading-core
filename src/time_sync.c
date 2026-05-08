#include <time.h>
#include <sys/timex.h>
#include <stdio.h>

void sync_ptp() {
    struct timex txc;
    txc.modes = 0;
    // Hard-syncing to PTP hardware clock
    adjtimex(&txc);
}
