import os

path = 'src/main.py'
with open(path, 'r') as f:
    lines = f.readlines()

new_dashboard_logic = [
    '    def _get_status_icon(self, component: str) -> str:\n',
    '        \"\"\"Helper to return dynamic status icons including Probing states.\"\"\"\n',
    '        if component == \"ibkr\":\n',
    '            if hasattr(self, \"ibkr_client\") and self.ibkr_client and self.ibkr_client.isConnected(): return \"✅ [ONLINE]\"\n',
    '            if \"connect_ibkr\" in getattr(self, \"background_tasks\", {}): return \"🟡 [PROBING]\"\n',
    '            return \"❌ [OFFLINE]\"\n',
    '        if component == \"mt5\":\n',
    '            if hasattr(self, \"mt5_client\") and self.mt5_client and self.mt5_client.terminal_info(): return \"✅ [ONLINE]\"\n',
    '            if \"connect_mt5\" in getattr(self, \"background_tasks\", {}): return \"🟡 [PROBING]\"\n',
    '            return \"❌ [OFFLINE]\"\n',
    '        if component == \"qdb\":\n',
    '            if hasattr(self, \"qdb\") and self.qdb and self.qdb.is_active: return \"✅ [TSDB-LIVE]\"\n',
    '            return \"❌ [MEMORY-ONLY]\"\n',
    '        return \"❓\"\n',
    '\n'
]

# Find where TradingSystem class starts (usually after imports)
found_class = False
for i, line in enumerate(lines):
    if 'class TradingSystem:' in line:
        # Check if helper already exists
        if '_get_status_icon' in "".join(lines[i:i+50]):
             # Just replace the content
             pass
        else:
             lines.insert(i + 1, "".join(new_dashboard_logic))
        found_class = True
        break

# Force UTF-8 encoding in PowerShell if possible
for i, line in enumerate(lines):
    if 'if __name__ == \"__main__\":' in line:
        lines.insert(i + 1, '    import sys, io\n    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding=\"utf-8\")\n')
        break

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('SUCCESS: Universal Clarity & UTF-8 Enforcement Applied')
