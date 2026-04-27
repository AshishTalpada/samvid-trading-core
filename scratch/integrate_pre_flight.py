import sys

file_path = 'src/brain.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
found_place_order = False
found_bracket_call = False

for line in lines:
    # Look for the start of _place_ibkr_order
    if 'async def _place_ibkr_order' in line:
        found_place_order = True
    
    # Inject the pre-flight check right before the bracket order call
    if found_place_order and 'ids = await self.ibkr_conn.place_bracket_order' in line and not found_bracket_call:
        indent = line[:line.find('ids =')]
        new_lines.append(f"{indent}# --- SOVEREIGN PRE-FLIGHT ARMOR (V18.6) ---\n")
        new_lines.append(f"{indent}ok, reason = await asyncio.to_thread(self.ibkr_conn.validate_order_pre_flight, symbol, direction, shares, limit_price)\n")
        new_lines.append(f"{indent}if not ok:\n")
        new_lines.append(f"{indent}    logger.critical(f'🛑 PRE-FLIGHT REJECTION for {{symbol}}: {{reason}}')\n")
        new_lines.append(f"{indent}    return None\n\n")
        found_bracket_call = True
        
    new_lines.append(line)

if found_bracket_call:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("✓ brain.py Sovereign Pre-Flight SUCCESSFULLY INTEGRATED.")
else:
    print("🚨 FAILED: Order placement site not found in brain.py.")
