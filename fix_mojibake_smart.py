import os
import re

def fix_smart(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Aggressive Regex: find anything with Ã¢ and surrounding box/arrow markers
        fixed = content.replace('â• Â ', '═').replace('â†’', '→')
        fixed = fixed.replace('â•—', '╗').replace('â•š', '╚').replace('â•’', '╔')
        
        # Repair the specific dashboard line that uses "â• Â " repeatedly
        fixed = fixed.replace('â• Â ', '═')
        
        # Final cleanup for main.py specifically
        if 'main.py' in file_path:
             fixed = fixed.replace('â Œ', '❌').replace('â “', '⏳')
             fixed = fixed.replace('Ã¢ÂÂ±Ã¯Â¸Â', '⏱️')
             fixed = fixed.replace('âš ï¸ ï¸ ', '⚠️')
             fixed = fixed.replace('ðŸ•“Â ', '🕒')
             fixed = fixed.replace('ðŸ›‘', '🛑')
             fixed = fixed.replace('Ã¢Â Å’', '❌')
             fixed = fixed.replace('âœ…', '✅').replace('âœ“', '✓')
        
        if fixed != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed)
            print("CLEANED: " + file_path)
            return True
    except:
        pass
    return False

if __name__ == "__main__":
    fix_smart('src/main.py')
    fix_smart('src/data_pipeline.py')
