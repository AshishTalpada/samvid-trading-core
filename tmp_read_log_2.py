import sys
from collections import Counter

try:
    with open('tmp_debug2.txt', 'rb') as f:
        data = f.read()
    try:
        text = data.decode('utf-16le')
    except UnicodeDecodeError:
        text = data.decode('utf-8', errors='replace')
    
    lines = text.splitlines()
    c = Counter()
    for i, line in enumerate(lines):
        if 'VETO:' in line or 'FAIL:' in line or 'SUCCESS' in line or 'TRADE ENTRY' in line or '🚀' in line:
            clean = line.strip()
            print(clean)
            if 'VETO:' in clean:
                idx = clean.find('VETO:')
                c[clean[idx:]] += 1
            elif 'FAIL:' in clean:
                idx = clean.find('FAIL:')
                c[clean[idx:]] += 1
            elif 'SUCCESS' in clean:
                idx = clean.find('SUCCESS')
                c[clean[idx:]] += 1
            elif 'TRADE ENTRY' in clean:
                c['TRADE ENTRY'] += 1
    
    print("\\nSUMMARY:")
    if not c:
        print("NO VETOS OR TRADES YET.")
    for k, v in c.items():
        print(f"{k}: {v}")

except Exception as e:
    print("Log file empty or missing.")
