import os

replacements = {
    "â•”": "╔",
    "â•—": "╗",
    "â•‘": "║",
    "â• ": "╠",
    "â•£": "╣",
    "â•¦": "╦",
    "â•©": "╩",
    "â•¬": "╬",
    "â•š": "╚",
    "â• ": "═",
    "â•": "═",
    "ðŸŒŒ": "🌌",
    "âœ“": "✓",
    "✅": "✅",
    "âœ˜": "✘",
    "ðŸš€": "🚀",
    "ðŸ“Š": "📊",
    "ðŸ”Œ": "🔌",
    "ðŸª ": "🧠",
    "ðŸˆ ": "🐟",
    "ðŸ“ˆ": "📈",
    "ðŸ   ": "🏠",
    "âš¡": "⚡",
    "â Stopwatch": "⏱",
    "ðŸ›‘": "🛑",
    "ðŸ• ": "🕓",
    "ðŸ•": "🕓",
    "â”": "━",
    "ðŸ“‰": "📉",
    "ðŸ”„": "🔄",
    "â€“": "-",
    "—": "—",
    "â†’": "→",
    "âš ": "⚠️",
}


def fix_file(path):
    try:
        with open(path, "rb") as f:
            data = f.read()

        # Assume it's actually UTF-8 but contains mojibake
        content = data.decode("utf-8", errors="ignore")
        original = content

        for k, v in replacements.items():
            content = content.replace(k, v)

        if content != original:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  ✓ Fixed: {path}")
            return True
    except Exception as e:
        print(f"  ! Error: {path} ({e})")
    return False


if __name__ == "__main__":
    import os

    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print("=== TradingSystem Mojibake Fixer ===")
    count = 0
    # Walk through src directory
    for root, _dirs, files in os.walk("src"):
        for file in files:
            if file.endswith(".py"):
                if fix_file(os.path.join(root, file)):
                    count += 1

    print(f"\nTotal files sanitized: {count}")
