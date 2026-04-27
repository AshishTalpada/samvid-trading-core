import sys

file_path = 'src/brain.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
found_first = False
for line in lines:
    # Keep the first one (with my comment) but remove the second one (without the comment)
    if 'self._last_tick_price: dict[str, float] = {}' in line:
        if 'V18.5 Memory Fix' in line:
            new_lines.append(line)
            found_first = True
        else:
            # This is the redundant one, skip it
            continue
    else:
        new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("✓ Redundancy STERILIZED.")
