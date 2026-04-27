import os

def final_fix():
    FILE = 'src/main.py'
    with open(FILE, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Force fix these and surrounding broken lines regardless of regex match
    # Since I have the line numbers now
    lines[741] = '                        f"  Fix: Open MT5 → File → Login → verify credentials match .env"\\n'
    lines[1140] = '                            f"⚠️  *Background Task Crashed*\\nTask: {name}\\nError: {e!s}"\\n'
    lines[1193] = '                sign = "📈" if daily_pnl > 0 else "📉" if daily_pnl < 0 else "📊"\\n'
    lines[1196] = '                        f"🛑 <b>Trading System Shutting Down</b>\\n\\n"\\n'
    lines[1197] = '                        f"🕒 {datetime.now().strftime(\'%Y-%m-%d %H:%M:%S\')}\\n"\\n'
    lines[1198] = '                        f"────────────────────────────────────────\\n"\\n'
    lines[1201] = '                        f"🔄 <b>Trades Executed:</b> {trades_today}"\\n'

    with open(FILE, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("Final Hard-Reset Fix applied to src/main.py")

if __name__ == "__main__":
    final_fix()
