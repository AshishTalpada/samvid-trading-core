import sys

file_path = 'src/agent_c_ibkr.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
found = False
for line in lines:
    new_lines.append(line)
    if 'Calculates position size using the 8-Step SETO Paradox.' in line and not found:
        # Add the fix right after
        indent = line[:line.find('Calculates')]
        new_lines.append(f"{indent}# --- SOVEREIGN REALITY ALIGNMENT (V18.5) ---\n")
        new_lines.append(f"{indent}_raw_nav = kwargs.get('account_value', balance)\n")
        new_lines.append(f"{indent}balance = min(balance, _raw_nav)\n")
        new_lines.append(f"{indent}if balance > 2000000.0:\n")
        new_lines.append(f"{indent}    logger.warning(f'🏛️ SOVEREIGN GUARD: Detected outlier account value of ${{balance:,.2f}}. Capping at $2M for Safety.')\n")
        new_lines.append(f"{indent}    balance = 2000000.0\n")
        found = True

if found:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("✓ agent_c_ibkr.py Sovereign Reality Alignment SUCCESSFULLY INJECTED.")
else:
    print("🚨 FAILED: Target not found in raw file.")
