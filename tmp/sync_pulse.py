import os

path = 'src/main.py'
with open(path, 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'await self.send_telegram_notification(notification)' in line:
        # We inject a clean terminal print here
        injection = [
            '            # Sovereign Terminal Calibration (V9.99)\n',
            '            clean_dashboard = notification.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "").replace("<pre>", "").replace("</pre>", "")\n',
            '            print(clean_dashboard)\n'
        ]
        lines[i:i] = injection
        break

with open(path, 'w') as f:
    f.writelines(lines)
print('SUCCESS: Terminal Pulse Synced')
