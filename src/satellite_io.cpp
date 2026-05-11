#include <cmath>

// Total Electron Content (TEC) correction for LEO satellite downlinks
extern "C" double correct_ionospheric_delay(double raw_latency, double tec_units) {
    // Total Electron Content (TEC) correction for LEO satellite downlinks
    double delay_correction = 40.3 * tec_units / std::pow(1.5e9, 2); 
    return raw_latency - delay_correction;
}
