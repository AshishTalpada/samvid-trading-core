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
} dim3;

extern dim3 blockIdx;
extern dim3 blockDim;
extern dim3 threadIdx;

// Mock __ldg and __stcs for intellisense
static inline float __ldg(const float* ptr) { return *ptr; }
static inline void __stcs(float* ptr, float val) { *ptr = val; }

extern "C" unsigned cudaConfigureCall(dim3 gridDim, dim3 blockDim, size_t sharedMem = 0, void *stream = 0);

static inline void cudaDeviceSynchronize() {}
#endif

#endif
