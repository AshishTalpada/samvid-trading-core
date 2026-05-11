import os
import re

p1 = re.compile(r'.*PILLAR.*', re.IGNORECASE)

for root, dirs, files_in_dir in os.walk('src'):
    for file_name in files_in_dir:
        if file_name.endswith('.py'):
            file_path = os.path.join(root, file_name)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            lines = content.splitlines()
            new_lines = [line for line in lines if not (p1.search(line) and '#' in line)]
            
            if len(lines) != len(new_lines):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(new_lines) + '\n')
                print(f"Stripped comments from {file_path}")
