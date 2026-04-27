import sys
try:
    with open('src/brain.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if 'def _place_ibkr_order' in line:
            for j in range(i, min(len(lines), i+40)):
                print(repr(lines[j]))
            break
except Exception as e:
    pass
