import os

path = 'src/main.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

final_lines = []
for line in lines:
    if 'os.system(\"cls\")' in line or 'os.system(\"clear\")' in line:
        # Stop clearing the scrolling logs!
        continue
    final_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(final_lines)
print('SUCCESS: Terminal Scrolling Restored - No more log-wiping')
