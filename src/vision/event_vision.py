import numpy as np


class NeuroMorphicVision:
    """See charts with sub-ms spike-based precision (DVS Event Cameras)."""
    def process_spikes(self, spike_events: list[tuple]) -> float:
        # Instead of frames, process asynchronous brightness changes
        # Tuple: (x, y, timestamp_us, polarity)
        if not spike_events: return 0.0
        positive_spikes = sum(1 for e in spike_events if e[3] > 0)
        negative_spikes = sum(1 for e in spike_events if e[3] < 0)
        return (positive_spikes - negative_spikes) / len(spike_events)
