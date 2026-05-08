#include <iostream>
#include <cmath>
#include <stdint.h>
#include <map>

/**
 * Sovereign Entropy Audit Engine
 * Performs real-time Shannon Entropy verification of Quantis QRNG streams.
 * Prevents execution if entropy drops below 7.99 bits per byte, 
 * which would signal a hardware sensor failure or adversary tampering.
 */

extern "C" double compute_shannon_entropy(const uint8_t* data, size_t size) {
    if (size == 0) return 0.0;
    
    uint64_t counts[256] = {0};
    for (size_t i = 0; i < size; ++i) {
        counts[data[i]]++;
    }
    
    double entropy = 0.0;
    for (int i = 0; i < 256; ++i) {
        if (counts[i] > 0) {
            double p = (double)counts[i] / size;
            entropy -= p * (std::log(p) / std::log(2.0));
        }
    }
    
    return entropy;
}

extern "C" bool verify_entropy_health(const uint8_t* samples, size_t count, double threshold) {
    double entropy = compute_shannon_entropy(samples, count);
    
    if (entropy < threshold) {
        fprintf(stderr, "[RNG AUDIT] CRITICAL: Entropy drop detected (%.4f bits). Stopping generators.\n", entropy);
        return false;
    }
    
    return true;
}
