#include <cmath>
#include <vector>
#include <algorithm>

// Rosenstein's algorithm for calculating the Largest Lyapunov Exponent (LLE)
extern "C" double compute_lyapunov_exponent(const double* series, int n, int tau, int m) {
    if (n < m * tau) return 0.0;

    // 1. Phase space reconstruction
    int num_vectors = n - (m - 1) * tau;
    std::vector<std::vector<double>> phase_space(num_vectors, std::vector<double>(m));
    
    for (int i = 0; i < num_vectors; ++i) {
        for (int j = 0; j < m; ++j) {
            phase_space[i][j] = series[i + j * tau];
        }
    }

    double sum_log_divergence = 0.0;
    int valid_pairs = 0;

    // 2. Find nearest neighbors and track divergence
    for (int i = 0; i < num_vectors; ++i) {
        double min_dist = 1e9;
        int nearest_idx = -1;

        for (int j = 0; j < num_vectors; ++j) {
            if (abs(i - j) > tau) { // Exclude temporally close points
                double dist = 0.0;
                for (int d = 0; d < m; ++d) {
                    dist += std::pow(phase_space[i][d] - phase_space[j][d], 2);
                }
                if (dist > 0 && dist < min_dist) {
                    min_dist = dist;
                    nearest_idx = j;
                }
            }
        }

        // Check divergence after 1 time step
        if (nearest_idx != -1 && i + 1 < num_vectors && nearest_idx + 1 < num_vectors) {
            double div_dist = 0.0;
            for (int d = 0; d < m; ++d) {
                div_dist += std::pow(phase_space[i+1][d] - phase_space[nearest_idx+1][d], 2);
            }
            if (div_dist > 0) {
                sum_log_divergence += std::log(sqrt(div_dist) / sqrt(min_dist));
                valid_pairs++;
            }
        }
    }

    if (valid_pairs == 0) return 0.0;
    return sum_log_divergence / valid_pairs; // >0 implies chaos
}
