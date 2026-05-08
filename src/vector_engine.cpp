#include <immintrin.h>  // AVX2 SIMD intrinsics

// Deep Implementation: SIMD Accelerated Hyperdimensional Computing (HDC)
// Uses 256-bit AVX2 registers to compute bitwise Hamming distance for 
// ultra-fast vector similarity in hardware.
extern "C" double compute_hdc_similarity(const int* v1, const int* v2, int size) {
    if (size % 8 != 0) {
        // Fallback for non-aligned sizes
        int matches = 0;
        for(int i = 0; i < size; i++) {
            if(v1[i] == v2[i]) matches++;
        }
        return (double)matches / size;
    }

    int match_count = 0;
    
    // Process 8 integers (256 bits) at a time using AVX2
    for(int i = 0; i < size; i += 8) {
        // Load 256 bits into AVX registers
        __m256i vec1 = _mm256_loadu_si256((__m256i*)&v1[i]);
        __m256i vec2 = _mm256_loadu_si256((__m256i*)&v2[i]);
        
        // Compare integers for equality (sets bits to 1 where equal)
        __m256i cmp = _mm256_cmpeq_epi32(vec1, vec2);
        
        // Extract the MSB of each 32-bit integer into an 8-bit mask
        int mask = _mm256_movemask_epi8(cmp);
        
        // Count the number of 1-bits in the mask. 
        // Since each 32-bit match gives 4 bits in the mask (0xF),
        // we divide the population count by 4.
        match_count += _mm_popcnt_u32(mask) / 4;
    }

    return (double)match_count / size;
}
