import os

FILE_PATH = 'src/main.py'

# Replace known bad lines with correct versions
# (Line numbers from current main.py in terminal)
REPLACEMETS = {
    163: '        logger.debug(f"⏱️  PROFILER: {name.ljust(30)} | {self._marks[name] * 1000:7.2f}ms")',
    171: '            if "connect_ibkr" in self.background_tasks: return "🟡 [PROBING]"',
    172: '            return "❌"',
    175: '            if "connect_mt5" in self.background_tasks: return "🟡 [PROBING]"',
    176: '            return "❌"',
    179: '            return "❌"',
    180: '        return "⏳"',
    361: '            logger.warning("⚠️   LIVE TRADING MODE DETECTED!")',
    363: '            print("⚠️   WARNING: NOT IN PAPER TRADING MODE!")',
    375: '            print("\\n✓ Live trading mode confirmed\\n")',
    389: '                    logger.info("✓ Local LLM Service (Ollama) is active and running.")',
    394: '                        "❌ Ollama startup failed. System will fallback to cloud APIs if keys exist."',
    1040: '                f"🚀 <b>Trading System Online</b>\\n\\n"',
    1041: '                f"📊 Mode: <code>{self.mode.upper()}</code>\\n"',
    1042: '                f"🔌 IBKR: {ibkr_status}\\n"',
    1043: '                f"🔌 MT5: {mt5_status}\\n"',
    1044: '                f"🧠 DhatuOracle: {qdb_status}\\n"',
    1045: '                f"📈 OpenBB: {\'✅\' if (self._openbb_provider and self._openbb_provider.is_available) else \'❌\'}\\n"',
    1046: '                f"🐟 Native Swarm: {\'✅\' if (self._swarm_predictor and self._swarm_predictor.is_available) else \'❌\'}\\n"',
    1047: '                f"🕒 Startup time: {(datetime.now() - start_time).total_seconds():.2f}s\\n"',
    1048: '                f"🕒 {datetime.now().strftime(\'%Y-%m-%d %H:%M:%S\')}"',
    742: '                        f"  Fix: Open MT5 → File → Login → verify credentials match .env"',
    1132: '                        await self.send_telegram_notification(',
    1133: '                            f"⚠️  *Background Task Crashed*\\nTask: {name}\\nError: {e!s}"',
    1134: '                        )',
    1281: '        print("\\n" + "╔" + "═" * 78 + "╗")',
    1282: '        print("║" + "  🌌  THE SOVEREIGN SINGULARITY MATRIX (SETO V8.0)  ".center(78) + "║")',
    1283: '        print("╠" + "═" * 78 + "╣")',
    1284: '        print(',
    1285: '            "║"',
    1286: '            + f"  STATUS:   ACTIVE  |  MODE:     {self.mode.upper().center(10)}  |  TICK:  100Hz (0.01s)  ".center(',
    1287: '                78',
    1288: '            )',
    1289: '            + "║"',
    1290: '        )',
    1291: '        print("╠" + "═" * 38 + "╦" + "═" * 39 + "╣")',
    1292: '        print("║  COGNITIVE MINDS (A-M) Status        ║  SYSTEM INFRASTRUCTURE Diagnostics    ║")',
    1293: '        print("╠" + "═" * 38 + "╬" + "═" * 39 + "╣")',
    1294: '        print("║  A: Dhatu Oracle      →  [ONLINE]    ║  Q: QuestDB (TSDB)    →  [SYNCED]     ║")',
    1295: '        print("║  B: Trading Brain     →  [ACTIVE]    ║  I: IBKR (Broker)     →  [CONNECTED]  ║")',
    1296: '        print("║  C: Risk Agent        →  [VETTING]   ║  B: Intelligence Bus  →  [LISTENING]  ║")',
    1297: '        print("║  D: Evolution Mind    →  [LEARNING]  ║  G: Ghost Watchdog    →  [ARBITER]    ║")',
    1298: '        print("║  E: Data Pipeline     →  [STREAMING] ║  V: Vault Registry    →  [LOCKED]     ║")',
    1299: '        print("║  K: Ultrathink R-Res  →  [RESONANCE] ║  S: System Mind       →  [STABLE]     ║")',
    1300: '        print("║  M: Coordinator Phase →  [SOVEREIGN] ║  L: Ollama (Local AI) →  [GPU-ACTIVE]  ║")',
    1301: '        print("╚" + "═" * 38 + "╩" + "═" * 39 + "╝\\n")',
}

def repair_main():
    with open(FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    for line_no, new_content in REPLACEMETS.items():
        if line_no <= len(lines):
            # Convert 1-indexed to 0-indexed
            lines[line_no - 1] = new_content + '\n'
            print(f"Repaired line {line_no}")
        else:
            print(f"Line {line_no} out of range!")

    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        f.writelines(lines)

if __name__ == "__main__":
    repair_main()
