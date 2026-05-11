#include "cuda/cuda_runtime.h"

#ifdef _WIN32
#include <windows.h>
static inline int mlock(void* addr, size_t len) {
    return VirtualLock(addr, len) ? 0 : -1;
}
#else
#include <sys/mman.h>
#endif

#ifndef cudaMemAdviseSetReadMostly
#define cudaMemAdviseSetReadMostly 1
#endif

/**
 * Sovereign Native SLM (Small Language Model) Accelerator
 * Implements low-latency neural inference kernels for real-time 
 * market regime classification and micro-signal fusion.
 */

__global__ void slm_linear_silu_kernel(const float* __restrict__ input, 
                                       const float* __restrict__ weights,
                                       const float* __restrict__ bias,
                                       float* __restrict__ output,
                                       int in_dim, int out_dim) {
    // Shared memory to store the input vector for this block
    extern __shared__ float s_input[];
    
    // Cooperative load of input into shared memory
    for (int i = threadIdx.x; i < in_dim; i += blockDim.x) {
        s_input[i] = input[i];
    }
    __syncthreads();

    int row = blockIdx.x * blockDim.x + threadIdx.x;
    if (row < out_dim) {
        float sum = (bias != NULL) ? bias[row] : 0.0f;
        
        #pragma unroll 4
        for (int i = 0; i < in_dim; i++) {
            sum += s_input[i] * weights[row * in_dim + i];
        }
        
        // SiLU Activation (x * sigmoid(x))
        float sigmoid = 1.0f / (1.0f + expf(-sum));
        output[row] = sum * sigmoid;
    }
}

// Token Sampling Kernel (Argmax for now)
__global__ void slm_argmax_kernel(const float* __restrict__ logits, int* __restrict__ token_id, int vocab_size) {
    int tid = threadIdx.x;
    if (tid == 0) {
        float max_val = -1e9f;
        int max_idx = 0;
        for (int i = 0; i < vocab_size; i++) {
            if (logits[i] > max_val) {
                max_val = logits[i];
                max_idx = i;
            }
        }
        *token_id = max_idx;
    }
}

extern "C" void lock_vram_weights(void* ptr, size_t size) {
    // 1. Lock in physical RAM to prevent swapping (POSIX or Windows)
    mlock(ptr, size);
    
    // 2. Advise CUDA that these weights are read-only to optimize caching on L2
#ifdef __CUDACC__
    cudaMemAdvise(ptr, size, cudaMemAdviseSetReadMostly, 0);
#endif
}

extern "C" void run_slm_inference(float* d_input, float* d_weights, float* d_bias, float* d_output, int in_dim, int out_dim) {
    dim3 block = {256, 1, 1};
    dim3 grid = {(out_dim + block.x - 1) / block.x, 1, 1};
    size_t shared_mem = in_dim * sizeof(float);
    KERNEL_LAUNCH(slm_linear_silu_kernel, grid, block, shared_mem, 0, d_input, d_weights, d_bias, d_output, in_dim, out_dim);
}

extern "C" void run_slm_sampling(float* d_logits, int* d_token_id, int vocab_size) {
    dim3 block = {1, 1, 1};
    dim3 grid = {1, 1, 1};
    KERNEL_LAUNCH(slm_argmax_kernel, grid, block, 0, 0, d_logits, d_token_id, vocab_size);
}
