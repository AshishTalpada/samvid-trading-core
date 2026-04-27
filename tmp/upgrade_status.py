import os

path = 'src/main.py'
with open(path, 'r') as f:
    lines = f.readlines()

new_dashboard_logic = [
    '    def _get_status_icon(self, component: str) -> str:\n',
    '        \"\"\"Helper to return dynamic status icons including Probing states.\"\"\"\n',
    '        if component == \"ibkr\":\n',
    '            if hasattr(self, \"ibkr_client\") and self.ibkr_client and self.ibkr_client.isConnected(): return \"✅\"\n',
    '            if \"connect_ibkr\" in self.background_tasks: return \"🟡 [PROBING]\"\n',
    '            return \"❌\"\n',
    '        if component == \"mt5\":\n',
    '            if hasattr(self, \"mt5_client\") and self.mt5_client and self.mt5_client.terminal_info(): return \"✅\"\n',
    '            if \"connect_mt5\" in self.background_tasks: return \"🟡 [PROBING]\"\n',
    '            return \"❌\"\n',
    '        if component == \"qdb\":\n',
    '            if hasattr(self, \"qdb\") and self.qdb and self.qdb.is_active: return \"✅\"\n',
    '            return \"❌\"\n',
    '        return \"❓\"\n',
    '\n',
    '    async def _dashboard_pulse(self):\n',
    '        \"\"\"Periodically refresh the dashboard while brokers are probing.\"\"\"\n',
    '        import asyncio\n',
    '        for _ in range(12): # Monitor for the first 2 mins\n',
    '            await asyncio.sleep(10)\n',
    '            if not getattr(self, \"is_running\", True): break\n',
    '            self._display_dashboard()\n',
    '\n'
]

# Find where TradingSystem class starts (usually after imports)
found_class = False
for i, line in enumerate(lines):
    if 'class TradingSystem:' in line:
        # Join lines together correctly
        lines.insert(i + 1, ''.join(new_dashboard_logic))
        found_class = True
        break

# Now update the startup and _display_dashboard
for i, line in enumerate(lines or []):
    if 'asyncio.create_task(self._start_background_tasks())' in line:
        lines.insert(i + 1, '            asyncio.create_task(self._dashboard_pulse())\n')
    
    if 'ibkr_status = \"✅\" if (hasattr(self, \"ibkr_client\")' in line:
        # Replace the dynamic status generation with our helper
        lines[i]   = '            ibkr_status = self._get_status_icon(\"ibkr\")\n'
        lines[i+1] = '            mt5_status = self._get_status_icon(\"mt5\")\n'
        lines[i+2] = '            qdb_status = self._get_status_icon(\"qdb\")\n'

with open(path, 'w') as f:
    f.writelines(lines)
print('SUCCESS: Probing Logic & Pulse Dashboard Integrated')
