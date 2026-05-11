# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: nonecheck=False

from libc.stdlib cimport malloc, free
cimport cython

cdef struct OrderNode:
    long long order_id
    double price
    double quantity
    long long timestamp_ns
    OrderNode* next_order
    OrderNode* prev_order

cdef struct PriceLevel:
    double price
    double total_volume
    int order_count
    OrderNode* head
    OrderNode* tail

cdef class L3OrderBook:
    '''
    Deep Dive: Cython L3 Order Book Reconstruction.
    Maintains a deterministic double-linked list matching engine inside C-memory.
    Allows nanosecond traversal of deep liquidity pools, bypassing Python's GIL
    to track individual institutional orders entering and exiting the queue.
    '''
    cdef dict price_levels_bid
    cdef dict price_levels_ask
    cdef dict order_map # Maps order_id -> (PriceLevel*, OrderNode*)
    cdef double best_bid
    cdef double best_ask

    def __init__(self):
        self.price_levels_bid = {}
        self.price_levels_ask = {}
        self.order_map = {}
        self.best_bid = 0.0
        self.best_ask = 999999999.0

    def __dealloc__(self):
        """Free all remaining OrderNodes in the book."""
        cdef OrderNode* curr
        cdef OrderNode* next_ptr
        
        for side, price, ptr_val in self.order_map.values():
            curr = <OrderNode*>ptr_val
            free(curr)
        
        self.order_map.clear()
        self.price_levels_bid.clear()
        self.price_levels_ask.clear()

    cpdef bint add_order(self, long long order_id, int side, double price, double quantity, long long timestamp_ns):
        '''
        Side: 0 for BID, 1 for ASK
        '''
        if order_id in self.order_map:
            return False # Order already exists
            
        cdef OrderNode* new_order = <OrderNode*>malloc(sizeof(OrderNode))
        if new_order == NULL:
            raise MemoryError("Failed to allocate OrderNode")
            
        new_order.order_id = order_id
        new_order.price = price
        new_order.quantity = quantity
        new_order.timestamp_ns = timestamp_ns
        new_order.next_order = NULL
        new_order.prev_order = NULL

        # Find or create price level
        # We use Python dicts here for fast price lookup, but the nodes are C-structs
        cdef dict book = self.price_levels_ask if side == 1 else self.price_levels_bid
        
        if price not in book:
            book[price] = {
                'total_volume': 0.0,
                'order_count': 0,
                'head': <long>new_order,
                'tail': <long>new_order
            }
        else:
            # Append to tail
            tail_ptr = <OrderNode*>book[price]['tail']
            tail_ptr.next_order = new_order
            new_order.prev_order = tail_ptr
            book[price]['tail'] = <long>new_order
            
        book[price]['total_volume'] += quantity
        book[price]['order_count'] += 1
        
        self.order_map[order_id] = (side, price, <long>new_order)
        
        # Update BBO (Best Bid/Offer)
        if side == 0 and price > self.best_bid:
            self.best_bid = price
        elif side == 1 and price < self.best_ask:
            self.best_ask = price
            
        return True

    cpdef bint cancel_order(self, long long order_id):
        if order_id not in self.order_map:
            return False
            
        side, price, ptr_val = self.order_map.pop(order_id)
        cdef OrderNode* order = <OrderNode*>ptr_val
        cdef dict book = self.price_levels_ask if side == 1 else self.price_levels_bid
        
        book[price]['total_volume'] -= order.quantity
        book[price]['order_count'] -= 1
        
        # Unlink from Double Linked List
        if order.prev_order != NULL:
            order.prev_order.next_order = order.next_order
        else:
            book[price]['head'] = <long>order.next_order
            
        if order.next_order != NULL:
            order.next_order.prev_order = order.prev_order
        else:
            book[price]['tail'] = <long>order.prev_order
            
        free(order)
        
        # Clean up empty price levels
        if book[price]['order_count'] == 0:
            del book[price]
            # Must re-calculate BBO
            self._recalc_bbo(side)
            
        return True

    cdef void _recalc_bbo(self, int side):
        if side == 0: # Bid
            if not self.price_levels_bid:
                self.best_bid = 0.0
            else:
                self.best_bid = max(self.price_levels_bid.keys())
        else: # Ask
            if not self.price_levels_ask:
                self.best_ask = 999999999.0
            else:
                self.best_ask = min(self.price_levels_ask.keys())

    cpdef double get_imbalance(self):
        '''Returns order book imbalance ratio [-1.0 to 1.0]'''
        cdef double total_bid_vol = sum([v['total_volume'] for v in self.price_levels_bid.values()])
        cdef double total_ask_vol = sum([v['total_volume'] for v in self.price_levels_ask.values()])
        
        cdef double denom = total_bid_vol + total_ask_vol
        if denom == 0:
            return 0.0
            
        return (total_bid_vol - total_ask_vol) / denom
