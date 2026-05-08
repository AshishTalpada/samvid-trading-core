#include <cuda_runtime.h>

__global__ void hbm3_optimized_inference(float* w, float* x, float* out, int n) {
    // Target High Bandwidth Memory on H100 GPUs.
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if(i < n) out[i] = w[i] * x[i];
}
