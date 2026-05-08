#include "cuda_runtime.h"
#include <stdio.h>

/**
 * Sparse Compute Kernel
 * Focuses GPU compute only on "Moving" symbols, ignoring dead tickers.
 * Massively reduces power consumption and frees up CUDA cores for
 * high-volatility targets.
 */

__global__ void sparse_update_kernel(const float* prices, const int* active_mask, float* output, int N) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    
    // Only execute heavy compute if the mask is 1 (Active/Moving)
    if (idx < N && active_mask[idx] == 1) {
        // Simulated heavy neural network transformation
        float val = prices[idx];
        output[idx] = val * val * 0.99f; 
    }
}
