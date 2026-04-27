import os
import re

def fix_imports(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 1. Replace 'from src.module' with 'from module'
                new_content = re.sub(r'(\bfrom\s+)src\.', r'\1', content)
                new_content = re.sub(r'(\bimport\s+)src\.', r'\1', new_content)
                
                # 2. Replace 'from .module' with 'from module' (relative to flat src)
                new_content = re.sub(r'(\bfrom\s+)\.(\w+)', r'\1\2', new_content)
                
                if new_content != content:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"Fixed imports in {path}")

if __name__ == "__main__":
    fix_imports("src")
