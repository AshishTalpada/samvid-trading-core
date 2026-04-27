import os
import py_compile
import sys

def check_syntax(path):
    issues = []
    py_files = []
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith('.py'):
                py_files.append(os.path.join(root, file))
    
    for file in py_files:
        try:
            py_compile.compile(file, doraise=True)
            # print(f"PASS: {file}")
        except py_compile.PyCompileError as e:
            issues.append((file, str(e)))
        except Exception as e:
            issues.append((file, f"Error: {e}"))
    
    return issues, len(py_files)

if __name__ == "__main__":
    src_issues, src_count = check_syntax('src')
    tests_issues, tests_count = check_syntax('tests')
    
    total_issues = src_issues + tests_issues
    total_count = src_count + tests_count
    
    print(f"Checked {total_count} files ({src_count} in src, {tests_count} in tests).")
    
    if not total_issues:
        print("✅ No syntax errors found.")
    else:
        print(f"❌ Found {len(total_issues)} syntax errors:")
        for file, error in total_issues:
            print(f"\n--- {file} ---")
            print(error)
        sys.exit(1)
