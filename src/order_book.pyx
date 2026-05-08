# cython: boundscheck=False, wraparound=False
cdef class OrderBook:
    cdef public double best_bid
    cdef public double best_ask
    
    def calculate_imbalance(self) -> double:
        return (self.best_bid - self.best_ask) / (self.best_bid + self.best_ask + 1e-9)
