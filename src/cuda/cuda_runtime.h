#ifndef CUDA_RUNTIME_MOCK_H
#define CUDA_RUNTIME_MOCK_H

// Mock CUDA keywords and built-ins for IDE (clangd) intellisense
#if defined(__clang__) || !defined(__NVCC__)
#define __global__
#define __restrict__
#define __device__
#define __host__
#define __shared__

typedef struct {
    int x, y, z;
} dim3;

extern dim3 blockIdx;
extern dim3 blockDim;
extern dim3 threadIdx;

// Mock __ldg and __stcs for intellisense
static inline float __ldg(const float* ptr) { return *ptr; }
static inline void __stcs(float* ptr, float val) { *ptr = val; }

// Math mocks
#include <math.h>
#ifdef __cplusplus
extern "C" {
#endif
float expf(float x);
float sqrtf(float x);
#ifdef __cplusplus
}
#endif

extern "C" unsigned cudaConfigureCall(dim3 gridDim, dim3 blockDim, size_t sharedMem = 0, void *stream = 0);

#define KERNEL_LAUNCH(func, grid, block, ...) func(__VA_ARGS__)
#define SHARED_MEM

static inline void cudaDeviceSynchronize() {}
#else
#define KERNEL_LAUNCH(func, grid, block, ...) func<<<grid, block>>>(__VA_ARGS__)
#define SHARED_MEM __shared__
#endif

#endif
