class OrderObfuscator:
    """Obfuscate your order flow from institutional eyes."""
    def split_order(self, quantity: int) -> list[int]:
        return [quantity // 3, quantity // 3, quantity - 2 * (quantity // 3)]
