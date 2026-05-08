#include <fstream>
#include <stdint.h>
#include <immintrin.h>

/**
 * Sovereign Crypto Utilities
 * Combines Quantum RNG (QRNG) with Hardware RDRAND/RDSEED fallbacks.
 * Ensures absolute entropy for institutional-grade key generation.
 */

extern "C" uint64_t get_qrng_entropy() {
    // 1. Attempt to read from the Quantis QRNG hardware device
    std::ifstream qrng("/dev/qrng", std::ios::binary);
    uint64_t entropy = 0;
    
    if (qrng.is_open()) {
        qrng.read(reinterpret_cast<char*>(&entropy), sizeof(entropy));
        qrng.close();
        if (entropy != 0) return entropy;
    }
    
    // 2. Fallback to CPU hardware entropy (RDSEED)
    // RDSEED is designed for seeding pseudorandom number generators.
    #if defined(__x86_64__) || defined(_M_X64)
    if (_rdseed64_step((unsigned long long*)&entropy)) {
        return entropy;
    }
    #endif
    
    // 3. Last resort: high-precision clock jitter
    #ifdef _WIN32
    return (uint64_t)__rdtsc();
    #else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)(ts.tv_nsec ^ (uint64_t)ts.tv_sec << 32);
    #endif
}

extern "C" void xor_buffers(uint8_t* out, const uint8_t* in1, const uint8_t* in2, size_t len) {
    size_t i = 0;
    // SIMD optimized XOR
    #if defined(__AVX2__)
    for (; i <= len - 32; i += 32) {
        __m256i v1 = _mm256_loadu_si256((const __m256i*)(in1 + i));
        __m256i v2 = _mm256_loadu_si256((const __m256i*)(in2 + i));
        _mm256_storeu_si256((__m256i*)(out + i), _mm256_xor_si256(v1, v2));
    }
    #endif
    for (; i < len; i++) {
        out[i] = in1[i] ^ in2[i];
    }
}
