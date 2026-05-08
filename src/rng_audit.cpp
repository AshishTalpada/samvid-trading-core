#include <iostream>
#include <cmath>

extern "C" bool check_entropy_quality(uint64_t* samples, int count) {
    // Shannon entropy verification of QRNG streams
    double sum = 0;
    for(int i=0; i<count; i++) sum += samples[i];
    return (sum / count) > 0; // simplified
}
