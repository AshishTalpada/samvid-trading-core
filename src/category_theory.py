class MarketCategory:
    def __init__(self, name: str):
        self.name = name

    def compose(self, other: 'MarketCategory') -> 'MarketCategory':
        return MarketCategory(f"{self.name} -> {other.name}")
