import sys
import re
try:
    with open('tmp_debug2.txt', 'rb') as f:
        data = f.read()
    try:
        text = data.decode('utf-16le')
    except UnicodeDecodeError:
        text = data.decode('utf-8', errors='replace')
    
    clean_text = re.sub(r'\\x1b\[.*?m', '', text).replace('\\r', '')
    lines = clean_text.splitlines()
    for line in lines[-1000:]:
        if 'TRADE ENTRY' in line or 'Bracket PLACED' in line or 'Offline' in line or 'SUCCESS' in line:
            print(repr(line.strip()))
except Exception as e:
    pass
