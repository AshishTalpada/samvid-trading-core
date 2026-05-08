#include <cuda_runtime.h>
#include <sys/mman.h>

extern "C" void lock_vram_weights(void* ptr, size_t size) {
    mlock(ptr, size); // Prevent swapping to disk
    cudaMemAdvise(ptr, size, cudaMemAdviseSetReadMostly, 0);
}
