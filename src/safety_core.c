#include <stdatomic.h>
#include <stdbool.h>

/**
 * Sovereign Global Safety Core
 * Provides atomic signals that propagate across the entire polyglot system.
 * The GLOBAL_HALT signal is the ultimate circuit breaker.
 */

static atomic_bool global_halt_active = false;

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    double execution_latency_ms;
    double slippage_bps;
    int fill_count;
    bool hardware_fault;
} NativeTelemetry;

static NativeTelemetry latest_telemetry = {0};

void set_global_halt(bool state) {
    atomic_store(&global_halt_active, state);
}

bool is_global_halt_active() {
    return atomic_load(&global_halt_active);
}

void report_native_telemetry(double latency, double slippage, int fills, bool fault) {
    // Validate inputs
    if (latency < 0.0 || slippage < 0.0 || fills < 0) return;
    
    latest_telemetry.execution_latency_ms = latency;
    latest_telemetry.slippage_bps = slippage;
    latest_telemetry.fill_count = fills;
    latest_telemetry.hardware_fault = fault;
}

NativeTelemetry get_latest_telemetry() {
    return latest_telemetry;
}

#ifdef __cplusplus
}
#endif
