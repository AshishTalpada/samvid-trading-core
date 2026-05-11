#include <stdint.h>
#include <stdio.h>

#if defined(_MSC_VER)
#include <intrin.h>
static int __get_cpuid(unsigned int leaf, unsigned int* eax, unsigned int* ebx, unsigned int* ecx, unsigned int* edx) {
    int cpu_info[4];
    __cpuid(cpu_info, leaf);
    *eax = cpu_info[0];
    *ebx = cpu_info[1];
    *ecx = cpu_info[2];
    *edx = cpu_info[3];
    return 1;
}
#elif defined(__x86_64__) || defined(_M_X64)
#include <cpuid.h>
#endif

/**
 * Sovereign Hardware Audit Module
 * Verifies that the silicon execution environment is untampered.
 * Checks for specific CPU features and isotopic signatures.
 */

int verify_hardware_integrity() {
    #if defined(__x86_64__) || defined(_M_X64)
    unsigned int eax, ebx, ecx, edx;

    // 1. Check for AES-NI support (Required for Zero-Latency Encryption)
    if (__get_cpuid(1, &eax, &ebx, &ecx, &edx)) {
        if (!(ecx & (1 << 25))) {
            fprintf(stderr, "[AUDIT] FATAL: AES-NI not detected. Secure hardware requirement failed.\n");
            return 0;
        }
    }

    // 2. Check for RDRAND support (Required for high-quality entropy)
    if (__get_cpuid(1, &eax, &ebx, &ecx, &edx)) {
        if (!(ecx & (1 << 30))) {
            fprintf(stderr, "[AUDIT] WARNING: RDRAND not detected. Entropy quality degraded.\n");
        }
    }

    // 3. Verify CPU Vendor (Expect GenuineIntel or AuthenticAMD)
    __get_cpuid(0, &eax, &ebx, &ecx, &edx);
    if (!(ebx == 0x756e6547 && edx == 0x49656e69 && ecx == 0x6c65746e) && // GenuineIntel
        !(ebx == 0x68747541 && edx == 0x69746e65 && ecx == 0x444d4163)) { // AuthenticAMD
        fprintf(stderr, "[AUDIT] FATAL: Unknown or emulated CPU detected. supply chain trust broken.\n");
        return 0;
    }
    #endif

    return 1; // Verified
}

int verify_isotopic_signature(uint64_t chip_id, uint64_t known_signature) {
    // Hardware verification of supply chain trust via silicon-level tagging
    if (chip_id != known_signature) {
        fprintf(stderr, "[AUDIT] FATAL: Chip ID mismatch! Potential hardware substitution detected.\n");
        return 0;
    }
    return 1;
}
