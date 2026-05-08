# cython: boundscheck=False, wraparound=False
# align to 64-byte boundaries for L1 cache lines
cdef struct CacheAlignedTick:
    double price      # 8 bytes
    double volume     # 8 bytes
    long timestamp    # 8 bytes
    long order_id     # 8 bytes
    long flags        # 8 bytes
    double padding[3] # 24 bytes (Total = 64 bytes)
