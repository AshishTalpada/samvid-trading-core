#include <cmath>

extern "C" double compute_lyapunov_exponent(double* series, int n) {
    double exp = 0.0;
    for(int i = 0; i < n-1; i++) {
        exp += std::log(std::abs(series[i+1] - series[i]) + 1e-9);
    }
    return exp / n;
}
