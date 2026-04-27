import sys

file_path = 'src/agent_c_ibkr.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
found_class = False
found_marker = False

for line in lines:
    new_lines.append(line)
    
    # Inject the check logic into the IBKRConnection class
    if 'class IBKRConnection:' in line:
        found_class = True
        
    if found_class and 'def' in line and not found_marker:
        # We find the first method and inject our pre-flight BEFORE it or after init
        # Insertion Point: Right after the is_extended_hours I added earlier
        if 'def is_extended_hours' in line:
             # Wait, I'll find the END of is_extended_hours or just after it
             pass

    if 'return now < market_open or now > market_close' in line and not found_marker:
        indent = "    "
        new_lines.append(f"\n{indent}def validate_order_pre_flight(self, symbol: str, direction: str, shares: int, price: float, account_id: str = None) -> tuple[bool, str]:\n")
        new_lines.append(f"{indent}    \"\"\"Institutional Pre-Flight Armor (V18.6).\"\"\"\n")
        new_lines.append(f"{indent}    try:\n")
        new_lines.append(f"{indent}        # 1. Account Alignment\n")
        new_lines.append(f"{indent}        from config import IBKR_ACCOUNT_ID\n")
        new_lines.append(f"{indent}        target_acc = account_id or IBKR_ACCOUNT_ID.strip()\n")
        new_lines.append(f"{indent}        if target_acc and target_acc not in self.ib.wrapper.accounts:\n")
        new_lines.append(f"{indent}            return False, f'ACCOUNT_MISMATCH: Target {{target_acc}} not found in broker session.'\n\n")
        
        new_lines.append(f"{indent}        # 2. Purchasing Power Guard\n")
        new_lines.append(f"{indent}        nav = self.get_account_value()\n")
        new_lines.append(f"{indent}        order_value = shares * price\n")
        new_lines.append(f"{indent}        if order_value > nav * 2.0:  # Allow 2x margin maximum\n")
        new_lines.append(f"{indent}            return False, f'MARGIN_VIOLATION: Order value ${{order_value:,.2f}} exceeds 2x NAV (${{nav:,.2f}}).'\n\n")
        
        new_lines.append(f"{indent}        # 3. Temporal Execution Awareness\n")
        new_lines.append(f"{indent}        is_eth = self.is_extended_hours()\n")
        new_lines.append(f"{indent}        if is_eth:\n")
        new_lines.append(f"{indent}             logger.info(f'🏛️ ETH MODE: Order for {{symbol}} detected Post-Market. outsideRth will be FORCED.')\n\n")
        
        new_lines.append(f"{indent}        return True, 'PROCEED'\n")
        new_lines.append(f"{indent}    except Exception as e:\n")
        new_lines.append(f"{indent}        return False, f'PRE_FLIGHT_CRASH: {{e}}'\n")
        found_marker = True

if found_marker:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("✓ agent_c_ibkr.py Pre-Flight Guard SUCCESSFULLY INJECTED.")
else:
    print("🚨 FAILED: Target not found in raw file.")
