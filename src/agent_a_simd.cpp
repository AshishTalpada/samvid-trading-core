#include <immintrin.h>
#include <cmath>

extern "C" void compute_log_returns(double* prices, double* returns, int size) {
    // AVX-512 SIMD processing of returns
    for(int i = 0; i < size - 8; i+=8) {
        __m512d p1 = _mm512_loadu_pd(&prices[i]);
        __m512d p2 = _mm512_loadu_pd(&prices[i+1]);
        __m512d div = _mm512_div_pd(p2, p1);
        // Log approximation omitted for brevity
        _mm512_storeu_pd(&returns[i], div);
    }
}
