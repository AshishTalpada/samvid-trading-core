# cython: boundscheck=False, wraparound=False, nonecheck=False, cdivision=True
from libc.stdlib cimport malloc, free
import numpy as np
cimport numpy as cnp

cdef struct Level:
    double price
    double volume

cdef class OrderBook:
    cdef Level* bids
    cdef Level* asks
    cdef int bid_count
    cdef int ask_count
    cdef int max_levels
    
    def __cinit__(self, int max_levels=100):
        self.max_levels = max_levels
        self.bids = <Level*>malloc(max_levels * sizeof(Level))
        self.asks = <Level*>malloc(max_levels * sizeof(Level))
        self.bid_count = 0
        self.ask_count = 0
        
        for i in range(max_levels):
            self.bids[i].price = 0.0
            self.bids[i].volume = 0.0
            self.asks[i].price = 0.0
            self.asks[i].volume = 0.0
            
    def __dealloc__(self):
        free(self.bids)
        free(self.asks)

    cpdef void update_bid(self, double price, double volume, int level):
        if level < self.max_levels:
            self.bids[level].price = price
            self.bids[level].volume = volume
            if level + 1 > self.bid_count:
                self.bid_count = level + 1

    cpdef void update_ask(self, double price, double volume, int level):
        if level < self.max_levels:
            self.asks[level].price = price
            self.asks[level].volume = volume
            if level + 1 > self.ask_count:
                self.ask_count = level + 1

    cpdef double calculate_imbalance(self, int depth=5):
        """
        Microstructure: Calculate Volume Imbalance over the top N levels.
        Value > 0 means bid heavy (bullish).
        Value < 0 means ask heavy (bearish).
        """
        cdef double total_bid_vol = 0.0
        cdef double total_ask_vol = 0.0
        cdef int limit = min(depth, self.bid_count)
        
        for i in range(limit):
            total_bid_vol += self.bids[i].volume
            
        limit = min(depth, self.ask_count)
        for i in range(limit):
            total_ask_vol += self.asks[i].volume
            
        cdef double total = total_bid_vol + total_ask_vol
        if total == 0.0:
            return 0.0
            
        return (total_bid_vol - total_ask_vol) / total
