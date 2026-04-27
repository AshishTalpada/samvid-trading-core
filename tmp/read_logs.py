with open("logs/trading_system.log", "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

# Get the last 100 lines
tail = lines[-100:]

with open("tmp/log_tail.txt", "w", encoding="utf-8") as f:
    for line in tail:
        f.write(line)

print(f"Wrote last 100 lines (from line {len(lines)-100+1}) to tmp/log_tail.txt")
