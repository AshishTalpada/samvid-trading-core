import sys
import os

def fix_config():
    path = 'src/config.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Revert capital to 1M
    content = content.replace('Set to $500 for Real Account Scaling (V18.5 Hard-Cap)', 'Set to $1,000,000 for Paper Trading Vetting')
    content = content.replace('STARTING_CAPITAL_CAD = float(Vault.get("TOTAL_CAPITAL", "500.0"))', 'STARTING_CAPITAL_CAD = float(Vault.get("TOTAL_CAPITAL", "1000000.0"))')
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✓ config.py Budget Restored to $1M.")

def fix_sizer():
    path = 'src/agent_c_ibkr.py'
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    skip = False
    for line in lines:
        if 'SOVEREIGN SAFETY GATE (V18.5)' in line:
            skip = True
            continue
        if skip and 'balance = 500.0' in line:
            # We skip the rest of the if block
            continue
        if skip and 'if balance > 10000.0:' in line:
            continue
        if skip and 'logger.warning' in line:
            continue
        
        # Also fix the nav cap
        if 'nav = min(kwargs.get("account_value", balance), balance)' in line:
            line = line.replace('min(kwargs.get("account_value", balance), balance)', 'kwargs.get("account_value", balance)')
            
        new_lines.append(line)
        if skip and '# Step 1' in line: # Safety gate is usually before Step 1
            skip = False

    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("✓ agent_c_ibkr.py Safety Gate Sterilized.")

if __name__ == "__main__":
    fix_config()
    fix_sizer()
