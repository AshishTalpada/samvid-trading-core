import os
import sys
import py_compile
from pathlib import Path

def audit_project(root_path):
    print(f"--- Starting Complete Project Project Audit: {root_path} ---")
    
    python_files = []
    for root, dirs, files in os.walk(root_path):
        if any(x in root for x in ['node_modules', '.venv', 'venv', 'site-packages', '.git', '__pycache__']):
            continue
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    print(f"Found {len(python_files)} Python files.")
    
    # 1. Syntax Check
    errors = []
    for py_file in python_files:
        try:
            py_compile.compile(py_file, doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(f"SYNTAX ERROR: {py_file}\n{e}")
        except Exception as e:
            errors.append(f"COMPILE ERROR: {py_file}\n{e}")
            
    # 2. Basic Static Analysis (Check for common issues)
    # (Just a simple grep for undefined variables or suspicious patterns if we had more tools, but for now we rely on compilation)
    
    print(f"Syntax Check: {'PASSED' if not errors else 'FAILED'}")
    for err in errors:
        print(err)
        
    print(f"--- Audit Complete. Errors: {len(errors)} ---")

if __name__ == "__main__":
    audit_project('c:/Users/talpa/Desktop/System_Beta/TradingSystem')
