# cython: boundscheck=False, wraparound=False
cdef class Tick:
    cdef public double price
    cdef public double volume
    cdef public long timestamp

    def __init__(self, double p, double v, long t):
        self.price = p
        self.volume = v
        self.timestamp = t
