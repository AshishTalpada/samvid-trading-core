import sys
from datetime import datetime
import pytz

def inject_swarm_guard():
    path = 'src/swarm_predictor.py'
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    found_init = False
    found_forecast = False
    
    for line in lines:
        new_lines.append(line)
        
        # Inject the helper into the class
        if 'class SwarmPredictor:' in line:
            found_init = True
            
        if found_init and 'def __init__' in line:
            indent = "    "
            new_lines.append(f"{indent}def is_market_active(self) -> bool:\n")
            new_lines.append(f"{indent}    \"\"\"Checks if the US market is currently in high-liquidity session.\"\"\"\n")
            new_lines.append(f"{indent}    import pytz\n")
            new_lines.append(f"{indent}    tz = pytz.timezone('US/Eastern')\n")
            new_lines.append(f"{indent}    now = datetime.now(tz)\n")
            new_lines.append(f"{indent}    if now.weekday() >= 5: return False\n")
            new_lines.append(f"{indent}    market_open = now.replace(hour=9, minute=0, second=0, microsecond=0) # Incl. Pre-market lite\n")
            new_lines.append(f"{indent}    market_close = now.replace(hour=17, minute=0, second=0, microsecond=0) # Incl. Post-market lite\n")
            new_lines.append(f"{indent}    return market_open < now < market_close\n\n")
            found_init = False # Only inject once
            
        # Inject the Guard into get_market_forecast
        if 'async def get_market_forecast' in line:
            found_forecast = True
            
        if found_forecast and 'if not self._available:' in line:
            indent = "        "
            new_lines.append(f"{indent}# --- V18.6: HARDWARE PRESERVATION GUARD ---\n")
            new_lines.append(f"{indent}if not self.is_market_active():\n")
            new_lines.append(f"{indent}    logger.info(f'🏺 HARDWARE GUARD: US Market Inactive. Bypassing GPU Swarm debate for {{symbol}} to preserve VRAM.')\n")
            new_lines.append(f"{indent}    return self._neutral_consensus('Market Inactive (Hardware Preservation Active)')\n\n")
            found_forecast = False

    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("✓ swarm_predictor.py Hardware Preservation SUCCESSFULLY INJECTED.")

if __name__ == "__main__":
    inject_swarm_guard()
