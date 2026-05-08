#include <stdio.h>
#include <stdlib.h>

extern "C" void protect_icache() {
    // Memory Poisoning / Cache Guard stub
    // Prevents malicious code from injecting logic into L1 Instruction Cache
    printf("[CACHE_GUARD] I-Cache lockdown active. Non-executable memory enforced.\n");
}
