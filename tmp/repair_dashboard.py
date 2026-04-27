import os

path = 'src/main.py'
with open(path, 'r') as f:
    lines = f.readlines()

new_dashboard = [
    '    def print_dashboard(self) -> None:\n',
    '        \"\"\"Print a high-performance visual dashboard (Sovereign V9.99 Live)\"\"\"\n',
    '        ibkr_status = \"✅\" if (hasattr(self, \"ibkr_client\") and self.ibkr_client and self.ibkr_client.isConnected()) else \"❌\"\n',
    '        mt5_status = \"✅\" if (hasattr(self, \"mt5_client\") and self.mt5_client and self.mt5_client.terminal_info()) else \"❌\"\n',
    '        qdb_status = \"✅\" if (hasattr(self, \"qdb\") and self.qdb and self.qdb.is_active) else \"❌\"\n',
    '        swarm_status = \"✅\" if (getattr(self, \"_swarm_predictor\", None) and self._swarm_predictor.is_available) else \"❌\"\n',
    '        openbb_status = \"✅\" if (getattr(self, \"_openbb_provider\", None) and self._openbb_provider.is_available) else \"❌\"\n',
    '\n',
    '        print(\"\\n\" + \"=\" * 60)\n',
    '        print(f\"📊  Mode: {self.mode.upper()}\")\n',
    '        print(f\"🔌  IBKR: {ibkr_status}\")\n',
    '        print(f\"🔌  MT5: {mt5_status}\")\n',
    '        print(f\"🧠  DhatuOracle: {qdb_status}\")\n',
    '        print(f\"📈  OpenBB: {openbb_status}\")\n',
    '        print(f\"🐟  Native Swarm: {swarm_status}\")\n',
    '        print(f\"⚡️  HFT Streamer: ✅ {\'(Live TSDB)\' if (hasattr(self, \"qdb\") and self.qdb and self.qdb.is_active) else \'(Memory-Only)\'} \")\n',
    '        print(f\"🕒  {self.start_time.strftime(\'%Y-%m-%d %H:%M:%S\')}\")\n',
    '        print(\"=\" * 60 + \"\\n\")\n'
]

start = -1
end = -1
for i, line in enumerate(lines):
    if 'def print_dashboard' in line:
        start = i
    if start != -1 and i > start and (line.strip().startswith('def ') or line.strip().startswith('async def ')):
        end = i
        break

if start != -1 and end != -1:
    lines[start:end] = new_dashboard
    with open(path, 'w') as f:
        f.writelines(lines)
    print('SUCCESS: Dashboard Synchronized')
else:
    print('ERROR: Dashboard not found')
