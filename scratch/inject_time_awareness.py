import sys
from datetime import datetime
import pytz

def inject_time_awareness():
    path = 'src/agent_c_ibkr.py'
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    found_imports = False
    
    for line in lines:
        if 'import asyncio' in line and not found_imports:
            new_lines.append(line)
            new_lines.append("import pytz  # Added for Temporal Intelligence\n")
            found_imports = True
            continue
        
        # Inject the is_extended_hours helper into the IBKRConnection class
        if 'def _setup_callbacks(self) -> None:' in line:
            new_lines.append("    def is_extended_hours(self) -> bool:\n")
            new_lines.append("        \"\"\"Determines if current time is outside RTH (9:30 AM - 4:00 PM ET).\"\"\"\n")
            new_lines.append("        tz = pytz.timezone('US/Eastern')\n")
            new_lines.append("        now = datetime.now(tz)\n")
            new_lines.append("        if now.weekday() >= 5: return True  # Weekend\n")
            new_lines.append("        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)\n")
            new_lines.append("        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)\n")
            new_lines.append("        return now < market_open or now > market_close\n\n")
        
        # Inject the outsideRth flag into calculations
        if 'o = MarketOrder(direction, shares)' in line:
            new_lines.append(line)
            new_lines.append("                        o.outsideRth = self.is_extended_hours()\n")
            continue
            
        if 'o = LimitOrder(direction, shares, lmt)' in line:
            new_lines.append(line)
            new_lines.append("                        o.outsideRth = self.is_extended_hours()\n")
            continue

        new_lines.append(line)

    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("✓ agent_c_ibkr.py Temporal Intelligence SUCCESSFULLY INJECTED.")

if __name__ == "__main__":
    inject_time_awareness()
