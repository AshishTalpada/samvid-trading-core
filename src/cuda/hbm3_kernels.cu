#include "cuda_runtime.h"

/**
 * HBM3 Optimized Memory Kernel for NVIDIA H100
 * Bypasses L2 cache (using __ldg and streaming stores) to maximize 
 * the 3.2 TB/s bandwidth of High Bandwidth Memory when evaluating 
 * millions of market hyper-vectors in parallel.
 */

__global__ void hbm_optimized_vector_dot(const float* __restrict__ A, const float* __restrict__ B, float* __restrict__ C, int N) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < N) {
        // Force Load-Through-Cache (Stream) to prevent L2 thrashing
        float a = __ldg(&A[idx]);
        float b = __ldg(&B[idx]);
        
        // Compute
        float result = a * b;
        
        // Streaming store (Cache Bypass) directly to HBM
        __stcs(&C[idx], result);
    }
}

extern "C" void launch_hbm_kernel(float* d_A, float* d_B, float* d_C, int N) {
    int threads = 256;
    int blocks = (N + threads - 1) / threads;
    KERNEL_LAUNCH(hbm_optimized_vector_dot, blocks, threads, d_A, d_B, d_C, N);
    cudaDeviceSynchronize();
}
