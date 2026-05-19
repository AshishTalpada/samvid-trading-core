import logging
from datetime import datetime

import pyttsx3

logger = logging.getLogger(__name__)


class AudioJournal:
    """Psychology edge: System talks to you at the end of the day."""

    def __init__(self):
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 170)
        self.engine.setProperty("voice", "english-us")

    def narrate_day(self, pnl: float, trades: int, mistakes: int):
        date_str = datetime.now().strftime("%A, %B %d")
        script = f"Good evening, Architect. Today is {date_str}. "
        script += f"You executed {trades} trades. "

        if pnl > 0:
            script += f"The system secured a profit of ${pnl:,.2f}. "
        else:
            script += f"The system experienced a drawdown of ${abs(pnl):,.2f}. "

        if mistakes > 0:
            script += f"I detected {mistakes} psychological stress violations. We must review these to prevent reflexivity cascade. "
        else:
            script += "Your discipline was flawless. The Sovereign architecture remains stable."

        logger.info("Narrating Daily Journal.")
        self.engine.say(script)
        self.engine.runAndWait()
