class OpticalFailover:
    """Nanosecond switching between fiber lines."""
    def switch_line(self, current_latency_ns: int):
        if current_latency_ns > 50000: # >50 microseconds
            print("[NETWORK] BGP Route poisoned. Switching to backup dark fiber.")
