import os
import re

with open('src/main.py', 'rb') as f:
    data = f.read()

# Replace specifically identified mojibake by regex matching surrounding ASCII
# ⚠️  *Background Task Crashed*
data = re.sub(b'\xc3\xa2\xc2\x9a\xc2\xa0\xc3\xaf\xc2\xb8\xc2\x8f\s+\*Background Task Crashed\*', b'\xe2\x9a\xa0  *Background Task Crashed*', data)

# 🛑 <b>Trading System Shutting Down</b>
data = re.sub(b'\xc3\xb0\xc2\x9f\xc2\x9b\xc2\x91\s+<b>Trading System Shutting Down</b>', b'\xf0\x9f\x9b\x91 <b>Trading System Shutting Down</b>', data)

# 🕒 
data = re.sub(b'\xc3\xb0\xc2\x9f\xc2\x95\xc2\x93\xc2\xa0', b'\xf0\x9f\x95\x93 ', data)

# Box lines
data = re.sub(b'\xc3\xa2\xc2\x94\xc2\xac', b'\xe2\x94\x80', data)

# sign
data = re.sub(b'\xc3\xb0\xc2\x9f\xc2\x93\xc2\x89', b'\xf0\x9f\x93\x89', data)

with open('src/main.py', 'wb') as f:
    f.write(data)

print("Final Fix Applied to src/main.py")
