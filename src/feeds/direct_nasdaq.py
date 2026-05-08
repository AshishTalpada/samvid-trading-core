class NasdaqITCHFeed:
    """Direct ITCH 5.0 binary protocol parser for Nasdaq tick data."""
    def parse_message(self, binary_msg: bytes) -> dict:
        msg_type = chr(binary_msg[0])
        if msg_type == 'A':  # Add Order
            return {"type": "ADD", "order_id": binary_msg[1:9]}
        elif msg_type == 'E':  # Order Executed
            return {"type": "EXECUTE", "order_id": binary_msg[1:9]}
        return {"type": "UNKNOWN"}
