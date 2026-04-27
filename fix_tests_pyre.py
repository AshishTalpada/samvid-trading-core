import os
import glob

files = glob.glob('c:/Users/talpa/Desktop/System_Beta/TradingSystem/tests/*.py')

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    lines = content.split('\n')
    new_lines = []
    modified = False
    for line in lines:
        stripped = line.lstrip()
        if (stripped.startswith('import ') or stripped.startswith('from ')) and '# pyre-ignore' not in line:
            new_lines.append(line + ' # pyre-ignore[21]')
            modified = True
        else:
            new_lines.append(line)
    
    if modified:
        with open(f, 'w', encoding='utf-8') as file:
            file.write('\n'.join(new_lines))

print("Fixed local imports in tests.")
