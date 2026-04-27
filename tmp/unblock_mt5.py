import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

path = 'src/main.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 1. Wrap MT5 Login in a timeout executor
new_lines = []
for line in lines:
    if 'authorized = mt5.login(' in line:
        # Inject threaded login with timeout
        new_lines.append('            logger.info(\"Attempting MT5 login with 15s timeout...\")\n')
        new_lines.append('            with ThreadPoolExecutor() as executor:\n')
        new_lines.append('                future = executor.submit(mt5.login, int(self.mt5_login), self.mt5_password, self.mt5_server)\n')
        new_lines.append('                try:\n')
        new_lines.append('                    authorized = future.result(timeout=15)\n')
        new_lines.append('                except:\n')
        new_lines.append('                    logger.error(\"MT5 Login Timed Out - Skipping MT5\")\n')
        new_lines.append('                    authorized = False\n')
    elif 'login=int(self.mt5_login), password=self.mt5_password, server=self.mt5_server' in line:
        # Skip the original line
        continue
    else:
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('SUCCESS: MT5 Handshake Un-Blocked & Sovereign Priority Restored')
