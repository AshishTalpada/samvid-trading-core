#include <xmmintrin.h>

extern "C" void l1_hot_load(const float* array, int size) {
    // Lock Quorum logic into L1 cache via prefetch
    // _MM_HINT_T0 brings the data into L1 cache immediately.
    for(int i = 0; i < size; i+= 16) {
        _mm_prefetch((const char*)&array[i], _MM_HINT_T0);
    }
}
