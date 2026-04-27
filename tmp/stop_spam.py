import os

path = 'src/main.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 1. Remove the Dashboard Pulse loop
new_lines = []
skip = False
for line in lines:
    if 'async def _dashboard_pulse(self):' in line:
        skip = True
        continue
    if skip and line.strip() == '':
        skip = False
        continue
    if not skip:
        new_lines.append(line)

# 2. Add Clear Screen and better formatting
for i, line in enumerate(new_lines):
    if 'def _display_dashboard(self) -> None:' in line:
        # Inject clear screen for a clean terminal feel
        new_lines.insert(i + 1, '        if os.name == \"nt\": os.system(\"cls\")\n        else: os.system(\"clear\")\n')
        break

# 3. Stop the pulse task from starting
final_lines = []
for line in new_lines:
    if 'asyncio.create_task(self._dashboard_pulse())' in line:
        continue
    final_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(final_lines)
print('SUCCESS: Dashboard Spam Removed & Clear Screen Added')
