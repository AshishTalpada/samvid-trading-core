import sys

file_path = 'src/agent_c_ibkr.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
found_shield = False

for line in lines:
    new_lines.append(line)
    
    # Expand the SHIELD failure feedback logic
    if '# --- SOVEREIGN SHIELD: FAILURE FEEDBACK (V14.4) ---' in line:
        found_shield = True
        
    if found_shield and "logger.error(f\"🛡️ SHIELD: Exit failure detected for {symbol}. Total Strikes: {current_fails + 1}\")" in line:
        indent = line[:line.find('logger.error')]
        # We use {{ }} to escape the f-string braces so they are written literally to the file
        new_lines.append(f"\n{indent}# --- V18.6: AUTONOMOUS POST-MORTEM ---")
        new_lines.append(f"\n{indent}reason = str(trade.log[-1].message) if trade.log else 'UNKNOWN REASON'")
        new_lines.append(f"\n{indent}try:")
        new_lines.append(f"\n{indent}    import sqlite3")
        new_lines.append(f"\n{indent}    conn = sqlite3.connect('trading_system.db')")
        new_lines.append(f"\n{indent}    conn.execute('INSERT INTO failure_post_mortem VALUES (?, ?, ?, ?, ?)', (datetime.now().isoformat(), symbol, trade.order.action, status, reason))")
        new_lines.append(f"\n{indent}    conn.commit()")
        new_lines.append(f"\n{indent}    conn.close()")
        new_lines.append(f"\n{indent}    logger.info(f\"📉 POST-MORTEM: Signal {{symbol}} failure recorded: {{reason}}\")")
        new_lines.append(f"\n{indent}except Exception as e:")
        new_lines.append(f"\n{indent}    logger.error(f\"🚨 POST-MORTEM FAILURE: {{e}}\")\n")
        found_shield = False # Complete the injection for this block

if found_shield == False:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("✓ agent_c_ibkr.py Post-Mortem Logic SUCCESSFULLY INJECTED.")
else:
    print("🚨 FAILED: Target Shield logic not found in agent_c_ibkr.py.")
