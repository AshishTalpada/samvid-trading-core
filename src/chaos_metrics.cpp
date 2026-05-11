#include <cmath>
#include <vector>

// Deep Dive: Chaos Theory & Non-linear Dynamics for HFT
// Computes the Largest Lyapunov Exponent (LLE) using Rosenstein's algorithm.
// If LLE > 0, the market is deterministic chaos (predictable short-term).
// If LLE <= 0, the market is a random walk or mean-reverting (unpredictable).

extern "C" {

    double compute_lyapunov_exponent(const double* time_series, int n, int embedding_dimension, int time_delay) {
        if (time_series == NULL || n <= 0 || embedding_dimension <= 0 || time_delay <= 0) {
            return 0.0;
        }
        if (n <= embedding_dimension * time_delay) {
            return 0.0;
        }

        // 1. Phase Space Reconstruction via Takens' Theorem
        int num_vectors = n - (embedding_dimension - 1) * time_delay;
        std::vector<double> phase_space(num_vectors * embedding_dimension);
        
        for (int i = 0; i < num_vectors; ++i) {
            for (int j = 0; j < embedding_dimension; ++j) {
                phase_space[i * embedding_dimension + j] = time_series[i + j * time_delay];
            }
        }

        double sum_lyapunov = 0.0;
        int valid_points = 0;

        // 2. Find nearest neighbors in the reconstructed phase space
        for (int i = 0; i < num_vectors; ++i) {
            double min_distance = 1e12;
            int nearest_idx = -1;

            for (int j = 0; j < num_vectors; ++j) {
                // Theiler window: ignore temporally correlated points (hot path)
                int time_diff = std::abs(i - j);
                if (__builtin_expect(time_diff > time_delay, 1)) { 
                    double dist_sq = 0.0;
                    int base_i = i * embedding_dimension;
                    int base_j = j * embedding_dimension;
                    for (int d = 0; d < embedding_dimension; ++d) {
                        double diff = phase_space[base_i + d] - phase_space[base_j + d];
                        dist_sq += diff * diff;
                    }
                    
                    if (dist_sq > 0 && dist_sq < min_distance) {
                        min_distance = dist_sq;
                        nearest_idx = j;
                    }
                }
            }

            // 3. Track orbital divergence over time
            if (nearest_idx != -1) {
                int evolution_time = 1; // Look forward 1 step
                if (i + evolution_time < num_vectors && nearest_idx + evolution_time < num_vectors) {
                    double evolved_dist_sq = 0.0;
                    int next_i = (i + evolution_time) * embedding_dimension;
                    int next_j = (nearest_idx + evolution_time) * embedding_dimension;
                    for (int d = 0; d < embedding_dimension; ++d) {
                        double diff = phase_space[next_i + d] - phase_space[next_j + d];
                        evolved_dist_sq += diff * diff;
                    }
                    
                    if (evolved_dist_sq > 0) {
                        // LLE = (1/t) * ln(dist(t) / dist(0))
                        double divergence = std::log(std::sqrt(evolved_dist_sq) / std::sqrt(min_distance));
                        sum_lyapunov += divergence;
                        valid_points++;
                    }
                }
            }
        }

        if (valid_points == 0) return 0.0;
        
        return sum_lyapunov / valid_points; 
    }
}
