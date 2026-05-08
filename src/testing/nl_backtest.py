import logging

logger = logging.getLogger(__name__)

class NLBacktestParser:
    """Parses natural language backtest instructions into structured strategy parameters."""
    DIRECTION_MAP = {"buying": "BUY", "selling": "SELL", "shorting": "SELL"}
    DAY_MAP = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
               "friday": 4, "saturday": 5, "sunday": 6}

    def parse(self, instruction: str) -> dict:
        tokens = instruction.lower().split()
        direction = "BUY"
        days = []
        for i, tok in enumerate(tokens):
            if tok in self.DIRECTION_MAP:
                direction = self.DIRECTION_MAP[tok]
            if tok in self.DAY_MAP:
                days.append(self.DAY_MAP[tok])
        logger.info(f"Parsed NL backtest: direction={direction} days={days}")
        return {"direction": direction, "days_of_week": days or list(range(5))}
