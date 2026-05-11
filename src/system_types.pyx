# cython: boundscheck=False, wraparound=False
# src/system_types.pyx

cdef class Tick:
    def __init__(self, double p, double v, long t):
        self.price = p
        self.volume = v
        self.timestamp = t

cdef class Order:
    def __init__(self, str symbol, str side, double qty, double price, str order_type, long timestamp):
        self.symbol = symbol
        self.side = side
        self.qty = qty
        self.price = price
        self.order_type = order_type
        self.timestamp = timestamp
