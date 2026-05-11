# src/system_types.pxd
# Cython Type Definitions for High-Performance Memory Locking

cdef class Tick:
    cdef public double price
    cdef public double volume
    cdef public long timestamp

cdef class Order:
    cdef public str symbol
    cdef public str side
    cdef public double qty
    cdef public double price
    cdef public str order_type
    cdef public long timestamp
