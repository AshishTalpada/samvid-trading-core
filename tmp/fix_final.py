p = r'c:\Users\talpa\Desktop\System_Beta\TradingSystem\src\main.py'
with open(p, 'rb') as f:
    data = f.read()

# Replace "â Œ" - we find the bytes:
# â in UTF-8 is c3 a2
#   in UTF-8 is 20
# Œ in UTF-8 is c5 92
target = b'\xc3\xa2\x20\xc5\x92' 
replacement = '❌'.encode('utf-8')

import os
print(f"File size: {len(data)}")
count = data.count(target)
print(f"Found {count} occurrences of {target}")

if count > 0:
    new_data = data.replace(target, replacement)
    with open(p, 'wb') as f:
        f.write(new_data)
    print("Repair successful.")
else:
    # Try another variation: â (0xE2 in cp1252) + Œ (0x8C in cp1252) 
    # but re-encoded as UTF-8
    # â (U+00E2) -> c3 a2
    # Œ (U+0152) -> c5 92
    # but wait, maybe it's literally the string "â Œ"
    print("Attempting literal string replace in UTF-8...")
    content = data.decode('utf-8', errors='ignore')
    if "â Œ" in content:
        print("Found literal string!")
        new_content = content.replace("â Œ", "❌")
        with open(p, 'w', encoding='utf-8') as f:
            f.write(new_content)
