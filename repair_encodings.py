import os
import re

# Mapping of mojibake to correct UTF-8 characters
MAPPINGS = {
    "âœ…": "✅",
    "â Œ": "❌",
    "ðŸš€": "🚀",
    "ðŸ“Š": "📊",
    "ðŸ”Œ": "🔌",
    "ðŸ§ ": "🧠",
    "ðŸ“ˆ": "📈",
    "ðŸ•’": "🕒",
    "â±ï¸ ": "⏱️",
    "ðŸŸ¢": "🟢",
    "â•”": "╔",
    "â• Â ": "═",
    "â•—": "╗",
    "â•‘": "║",
    "â• ": "╠",
    "â•£": "╣",
    "â•¦": "╦",
    "â•¬": "╬",
    "â•©": "╩",
    "â•š": "╚",
    "â ±ï¸ ": "⏱️",
    "ðŸŒŒ": "🌌",
    "ðŸ Ÿ": "🐟",
    "âš ï¸ ï¸ ": "⚠️",
    "ðŸš¨": "🚨",
    "âŒ": "⌛",
    "âšï¸ï¸ ": "⚠️",
    "âœ“": "✓",
    "Ã¢ÂÅ’": "❌",
    "â“": "⏳",
    "â€”": "—",

}

def repair_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        new_content = content
        for mojibake, real_char in MAPPINGS.items():
            new_content = new_content.replace(mojibake, real_char)
        
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Repaired: {file_path}")
            return True
    except Exception as e:
        print(f"Failed to repair {file_path}: {e}")
    return False

def main():
    src_dir = 'src'
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                repair_file(os.path.join(root, file))

if __name__ == "__main__":
    main()
