import os
import sys
from pathlib import Path

def check_circular_imports(directory):
    import importlib.util
    import ast

    files = list(Path(directory).glob("*.py"))
    imports = {}

    for file in files:
        module_name = file.stem
        with open(file, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read())
                module_imports = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            module_imports.append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            module_imports.append(node.module)
                imports[module_name] = module_imports
            except Exception:
                pass

    for module, deps in imports.items():
        for dep in deps:
            if dep in imports and module in imports[dep]:
                print(f"Potential circular import: {module} <-> {dep}")

if __name__ == "__main__":
    check_circular_imports("src")
