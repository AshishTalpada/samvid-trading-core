import sys

try:
    with open('tmp_debug.txt', 'rb') as f:
        data = f.read()
    # Replace null bytes that PowerShell injects or try decoding as UTF-16
    try:
        text = data.decode('utf-16le')
    except UnicodeDecodeError:
        text = data.decode('utf-8', errors='replace')
    print(text[-2000:])
except Exception as e:
    print(f"Error reading file: {e}")
