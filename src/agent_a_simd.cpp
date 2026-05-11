#include <immintrin.h>
#include <cmath>
#include <stdint.h>

/**
 * Agent-A SIMD Accelerator
 * Optimized for AVX-512 (Skylake-X / Ice Lake / H100)
 * Computes high-velocity log returns and volatility scaling factors 
 * across thousands of symbols in parallel.
 */

extern "C" void compute_log_returns_simd(const double* prices, double* returns, int size) {
    if (size <= 1) return;  // Need at least 2 prices for returns
    int i = 0;
    
    #if defined(__AVX512F__)
    // AVX-512 Path
    for(; i <= size - 8; i += 8) {
        __m512d p_current = _mm512_loadu_pd(&prices[i + 1]);
        __m512d p_prev = _mm512_loadu_pd(&prices[i]);
        __m512d ratio = _mm512_div_pd(p_current, p_prev);
        
        // Accurate Log Approx: log(x) = (x-1) - 0.5(x-1)^2 + 0.333(x-1)^3
        __m512d one = _mm512_set1_pd(1.0);
        __m512d x = _mm512_sub_pd(ratio, one);
        __m512d x2 = _mm512_mul_pd(x, x);
        __m512d x3 = _mm512_mul_pd(x2, x);
        
        __m512d term1 = x;
        __m512d term2 = _mm512_mul_pd(x2, _mm512_set1_pd(0.5));
        __m512d term3 = _mm512_mul_pd(x3, _mm512_set1_pd(0.333333333333));
        
        __m512d log_ret = _mm512_add_pd(_mm512_sub_pd(term1, term2), term3);
        _mm512_storeu_pd(&returns[i], log_ret);
    }
    #elif defined(__AVX2__)
    // AVX2 Path (4 doubles at a time)
    for(; i <= size - 4; i += 4) {
        __m256d p_current = _mm256_loadu_pd(&prices[i + 1]);
        __m256d p_prev = _mm256_loadu_pd(&prices[i]);
        __m256d ratio = _mm256_div_pd(p_current, p_prev);
        
        __m256d one = _mm256_set1_pd(1.0);
        __m256d x = _mm256_sub_pd(ratio, one);
        __m256d x2 = _mm256_mul_pd(x, x);
        __m256d x3 = _mm256_mul_pd(x2, x);
        
        __m256d term1 = x;
        __m256d term2 = _mm256_mul_pd(x2, _mm256_set1_pd(0.5));
        __m256d term3 = _mm256_mul_pd(x3, _mm256_set1_pd(0.333333333333));
        
        __m256d log_ret = _mm256_add_pd(_mm256_sub_pd(term1, term2), term3);
        _mm256_storeu_pd(&returns[i], log_ret);
    }
    #endif
    
    // Clean up remaining elements using standard math library
    for(; i < size - 1; i++) {
        returns[i] = std::log(prices[i+1] / prices[i]);
    }
}

extern "C" void apply_volatility_scaling_simd(double* signals, const double* vol, double target_vol, int size) {
    if (size <= 0 || target_vol < 1e-10) return;  // Prevent division by zero
    int i = 0;
    
    #if defined(__AVX512F__)
    __m512d v_target = _mm512_set1_pd(target_vol);
    for(; i <= size - 8; i += 8) {
        __m512d v_sig = _mm512_loadu_pd(&signals[i]);
        __m512d v_vol = _mm512_loadu_pd(&vol[i]);
        __m512d scale = _mm512_div_pd(v_target, v_vol);
        __m512d result = _mm512_mul_pd(v_sig, scale);
        _mm512_storeu_pd(&signals[i], result);
    }
    #elif defined(__AVX2__)
    __m256d v_target = _mm256_set1_pd(target_vol);
    for(; i <= size - 4; i += 4) {
        __m256d v_sig = _mm256_loadu_pd(&signals[i]);
        __m256d v_vol = _mm256_loadu_pd(&vol[i]);
        __m256d scale = _mm256_div_pd(v_target, v_vol);
        __m256d result = _mm256_mul_pd(v_sig, scale);
        _mm256_storeu_pd(&signals[i], result);
    }
    #endif
    
    for(; i < size; i++) {
        signals[i] = signals[i] * (target_vol / vol[i]);
    }
}
