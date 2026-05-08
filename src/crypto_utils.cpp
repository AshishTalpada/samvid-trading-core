#include <iostream>
#include <fstream>

extern "C" uint64_t get_qrng_entropy() {
    std::ifstream qrng("/dev/qrng", std::ios::binary);
    uint64_t entropy;
    qrng.read(reinterpret_cast<char*>(&entropy), sizeof(entropy));
    return entropy;
}
