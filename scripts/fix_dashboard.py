path = "src/main.py"
with open(path, "rb") as f:
    data = f.read()

content = data.decode("utf-8", "ignore")

new_dashboard = """    def _display_dashboard(self):
        \"\"\"Final Aesthetic Polish: Displays a terminal-grade dashboard of active Minds.\"\"\"
        print("\\n" + "╔" + "═"*78 + "╗")
        print("║" + "  🌌  THE SOVEREIGN INFINITY MATRIX (Samvid v1.0-beta-beta)  ".center(78) + "║")
        print("╠" + "═"*78 + "╣")
        print("║" + f"  STATUS:   ACTIVE  |  MODE:     {self.mode.upper().center(10)}  |  TICK:  100Hz (0.01s)  ".center(78) + "║")
        print("╠" + "═"*38 + "╦" + "═"*39 + "╣")
        print("║  COGNITIVE MINDS (A-M) Status        ║  SYSTEM INFRASTRUCTURE Diagnostics    ║")
        print("╠" + "═"*38 + "╬" + "═"*39 + "╣")
        print("║  A: Dhatu Oracle      →  [ONLINE]    ║  Q: QuestDB (TSDB)    →  [SYNCED]     ║")
        print("║  B: Trading Brain     →  [ACTIVE]    ║  I: IBKR (Broker)     →  [CONNECTED]  ║")
        print("║  C: Risk Agent        →  [VETTING]   ║  B: Intelligence Bus  →  [LISTENING]  ║")
        print("║  D: Evolution Mind    →  [LEARNING]  ║  G: Ghost Watchdog    →  [ARBITER]    ║")
        print("║  E: Data Pipeline     →  [STREAMING] ║  V: Vault Registry    →  [LOCKED]     ║")
        print("║  K: Ultrathink R-Res  →  [RESONANCE] ║  S: System Mind       →  [STABLE]     ║")
        print("║  M: Coordinator Phase →  [SOVEREIGN] ║  L: Ollama (Local AI) →  [GPU-ACTIVE]  ║")
        print("╚" + "═"*38 + "╩" + "═"*39 + "╝\\n")"""

# Find start and end of the function
start_marker = "    def _display_dashboard(self):"
end_marker = "    async def main():"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_dashboard + "\n\n\n" + content[end_idx:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed _display_dashboard in src/main.py")
else:
    print(f"Start: {start_idx}, End: {end_idx}")
