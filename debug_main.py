import os

with open('src/main.py', 'rb') as f:
    for i, line in enumerate(f):
        if b'\xc3\xa2' in line:
            # Show the bytes and the hex to avoid terminal corruption
            print(f"Line {i+1} CORRUPTED: {line.hex()}")
