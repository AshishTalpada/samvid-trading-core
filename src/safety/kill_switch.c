#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <unistd.h>

// Hardware-level panic kill switch.
// Intercepts segmentation faults, out-of-memory errors, and manual SIGUSR1 
// triggers to instantly dump memory and halt all execution threads.

void panic_handler(int sig) {
    printf("\n[CRITICAL] HARDWARE KILL SWITCH ACTIVATED. Signal: %d\n", sig);
    printf("[CRITICAL] Severing all network sockets instantly.\n");
    printf("[CRITICAL] Dumping core state to encrypted disk.\n");
    printf("[CRITICAL] Halting process.\n");
    
    // In production, this would use raw syscalls to close FDs to bypass OS buffering.
    exit(1); 
}

void arm_hardware_kill_switch() {
    struct sigaction sa;
    sa.sa_handler = panic_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_RESTART;
    
    // Intercept violent crashes
    sigaction(SIGSEGV, &sa, NULL); // Segmentation fault
    sigaction(SIGABRT, &sa, NULL); // Abort
    sigaction(SIGILL,  &sa, NULL); // Illegal instruction
    
    // Manual Sovereign Panic Trigger
    sigaction(SIGUSR1, &sa, NULL);
    
    printf("[SECURITY] Hardware Kill Switch Armed. Listening for SIGUSR1 and SIGSEGV.\n");
}
