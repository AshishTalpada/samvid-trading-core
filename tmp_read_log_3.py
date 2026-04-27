import sys
try:
    with open('tmp_debug2.txt', 'rb') as f:
        data = f.read()
    try:
        text = data.decode('utf-16le')
    except UnicodeDecodeError:
        text = data.decode('utf-8', errors='replace')
    
    lines = text.splitlines()
    for line in lines:
        if 'Mocking IBKR' in line or 'Failed to connect to IBKR' in line or 'Paper Mode' in line:
            print(line.strip())
except Exception as e:
    pass
