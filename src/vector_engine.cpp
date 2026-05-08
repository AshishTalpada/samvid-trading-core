#include <vector>
#include <random>

extern "C" double compute_hdc_similarity(int* v1, int* v2, int size) {
    int matches = 0;
    for(int i = 0; i < size; i++) {
        if(v1[i] == v2[i]) matches++;
    }
    return (double)matches / size;
}
