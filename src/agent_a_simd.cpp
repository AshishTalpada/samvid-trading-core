#include <immintrin.h>
#include <cmath>
#include <stdint.h>

/**
 * Agent-A SIMD Accelerator
 * Optimized for AVX-512 (Skylake-X / Ice Lake / H100)
 * Computes high-velocity log returns and volatility scaling factors 
 * across thousands of symbols in parallel.
 */

extern "C" void compute_log_returns_avx512(const double* prices, double* returns, int size) {
    // Process 8 double-precision floats at a time (512 bits)
    int i = 0;
    for(; i <= size - 8; i += 8) {
        // Load p[t] and p[t-1]
        __m512d p_current = _mm512_loadu_pd(&prices[i + 1]);
        __m512d p_prev = _mm512_loadu_pd(&prices[i]);
        
        // Compute p[t] / p[t-1]
        __m512d ratio = _mm512_div_pd(p_current, p_prev);
        
        // Log approximation (AVX-512 doesn't have native log, using polynomial approximation or SVML)
        // For HFT, we often use ln(x) approx = (x-1) - (x-1)^2/2 + (x-1)^3/3 for x near 1
        __m512d one = _mm512_set1_pd(1.0);
        __m512d x = _mm512_sub_pd(ratio, one); // x = (ratio - 1)
        
        __m512d x2 = _mm512_mul_pd(x, x);
        __m512d term2 = _mm512_mul_pd(x2, _mm512_set1_pd(0.5));
        
        __m512d log_ret = _mm512_sub_pd(x, term2);
        
        _mm512_storeu_pd(&returns[i], log_ret);
    }
    
    // Clean up remaining elements
    for(; i < size - 1; i++) {
        returns[i] = std::log(prices[i+1] / prices[i]);
    }
}

extern "C" void apply_volatility_scaling_avx512(double* signals, const double* vol, double target_vol, int size) {
    __m512d v_target = _mm512_set1_pd(target_vol);
    
    for(int i = 0; i <= size - 8; i += 8) {
        __m512d v_sig = _mm512_loadu_pd(&signals[i]);
        __m512d v_vol = _mm512_loadu_pd(&vol[i]);
        
        // scale = target_vol / vol
        __m512d scale = _mm512_div_pd(v_target, v_vol);
        __m512d result = _mm512_mul_pd(v_sig, scale);
        
        _mm512_storeu_pd(&signals[i], result);
    }
}
