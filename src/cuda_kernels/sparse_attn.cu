#include "cuda_runtime.h"
#include <math.h>

#define BLOCK_SIZE 256

// Deep implementation of Sparse Attention kernel targeted for HBM3
// Ignores computation of values where mask is 0 to save cycles.
__global__ void sparse_attention_kernel(const float* __restrict__ Q, 
                                        const float* __restrict__ K, 
                                        const float* __restrict__ V, 
                                        const int* __restrict__ sparsity_mask,
                                        float* __restrict__ out, 
                                        int seq_len, int dim) {
    
    int tid = threadIdx.x;
    int row = blockIdx.x * blockDim.x + tid;
    
    // Shared memory for K/V caching
#ifdef __NVCC__
    extern __shared__ float shared_mem[];
#else
    extern float shared_mem[];
#endif
    float* K_shared = shared_mem;
    float* V_shared = &shared_mem[BLOCK_SIZE * dim];

    if (row < seq_len) {
        float sum_exp = 0.0f;
        float max_score = -1e9f;

        // Phase 1: Compute scores and find max for numerical stability
        for (int j = 0; j < seq_len; ++j) {
            if (sparsity_mask[row * seq_len + j] == 1) { // Only compute if mask allows
                float score = 0.0f;
                for (int d = 0; d < dim; ++d) {
                    score += Q[row * dim + d] * K[j * dim + d];
                }
                score /= sqrtf((float)dim);
                if (score > max_score) max_score = score;
            }
        }

        // Phase 2: Compute softmax and output
        float out_val[256];
        for(int d=0; d<dim; ++d) out_val[d] = 0.0f;

        for (int j = 0; j < seq_len; ++j) {
            if (sparsity_mask[row * seq_len + j] == 1) {
                float score = 0.0f;
                for (int d = 0; d < dim; ++d) {
                    score += Q[row * dim + d] * K[j * dim + d];
                }
                score /= sqrtf((float)dim);
                
                float weight = expf(score - max_score);
                sum_exp += weight;

                for (int d = 0; d < dim; ++d) {
                    out_val[d] += weight * V[j * dim + d];
                }
            }
        }

        for (int d = 0; d < dim; ++d) {
            out[row * dim + d] = out_val[d] / sum_exp;
        }
    }
}
