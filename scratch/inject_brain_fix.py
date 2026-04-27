import sys

file_path = 'src/brain.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
found = False
for line in lines:
    new_lines.append(line)
    if 'self.state = TradingState.STANDBY' in line and not found:
        # Add the fix right after
        indent = line[:line.find('self.state')]
        new_lines.append(f"{indent}self._last_tick_price: dict[str, float] = {{}}  # V18.5 Memory Fix\n")
        found = True

if found:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("✓ Sovereign Memory-Seal SUCCESSFULLY INJECTED.")
else:
    print("🚨 FAILED: Target not found in raw file.")
