#ifndef CUDA_RUNTIME_MOCK_H
#define CUDA_RUNTIME_MOCK_H

// Mock CUDA keywords and built-ins for IDE (clangd) intellisense
#ifndef __CUDACC__
#define __global__
#define __restrict__
#define __device__
#define __host__

typedef struct {
    int x, y, z;
} dim3_mock;

extern dim3_mock blockIdx;
extern dim3_mock blockDim;
extern dim3_mock threadIdx;

// Mock __ldg and __stcs for intellisense
static inline float __ldg(const float* ptr) { return *ptr; }
static inline void __stcs(float* ptr, float val) { *ptr = val; }

static inline void cudaDeviceSynchronize() {}
#endif

#endif
