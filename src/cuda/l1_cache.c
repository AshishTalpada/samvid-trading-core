#include <stdio.h>

/**
 * L1 Cache Hot-Load mechanism.
 * Uses GCC/Clang built-in prefetch instructions to manually pull
 * the Quorum execution structures into the CPU L1 cache BEFORE
 * the market data arrives, eliminating cache-miss latency (~20ns).
 */

typedef struct {
    double entry_price;
    double current_volume;
    int execution_flag;
} HotLoopData;

void prefetch_quorum_logic(HotLoopData* data_array, int size) {
    if (data_array == NULL || size <= 0) return;  // Validate input
    
    for (int i = 0; i < size; i++) {
        // __builtin_prefetch(addr, rw, locality)
        // rw=0 (read), locality=3 (leave in L1 cache)
        __builtin_prefetch(&data_array[i], 0, 3);
    }
}

void execute_hot_loop(HotLoopData* data_array, int size) {
    if (data_array == NULL || size <= 0) return;  // Validate input
    
    // Because data is already in L1, this loop runs at maximum IPC.
    for (int i = 0; i < size; i++) {
        if (data_array[i].current_volume > 10000) {
            data_array[i].execution_flag = 1;
        }
    }
}
