import os
import re

def final_purge(file_path):
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
            
        # These are ALL the mojibake patterns we found
        replacements = [
            (b'\xc3\xa2\xc2\x9c\xc2\x85', '✅'.encode('utf-8')),
            (b'\xc3\xa2\xc2\x9c\xc2\x94', '✓'.encode('utf-8')),
            (b'\xc3\xb0\xc2\x9f\xc2\x9a\xc2\x80', '🚀'.encode('utf-8')),
            (b'\xc3\xb0\xc2\x9f\xc2\x93\xc2\x8a', '📊'.encode('utf-8')),
            (b'\xc3\xb0\xc2\x9f\xc2\x94\xc2\x8c', '🔌'.encode('utf-8')),
            (b'\xc3\xb0\xc2\x9f\xc2\xa7\xc2\xa0', '🧠'.encode('utf-8')),
            (b'\xc3\xb0\xc2\x9f\xc2\x93\xc2\x88', '📈'.encode('utf-8')),
            (b'\xc3\xb0\xc2\x9f\xc2\x95\xc2\x92', '🕒'.encode('utf-8')),
            (b'\xc3\xa2\xc2\x8f\xc2\xb1\xc3\xaf\xc2\xb8\xc2\x8f', '⏱️'.encode('utf-8')),
            (b'\xc3\xb0\xc2\x9f\xc2\x9f\xc2\xa2', '🟢'.encode('utf-8')),
            (b'\xc3\xa2\xc2\x9a\xc2\xa0\xc3\xaf\xc2\xb8\xc2\x8f', '⚠️'.encode('utf-8')),
            (b'\xc3\xb0\xc2\x9f\xc2\x9b\xc2\x91', '🛑'.encode('utf-8')),
            (b'\xc3\xb0\xc2\x9f\xc2\x9a\xc2\xa8', '🚨'.encode('utf-8')),
            (b'\xc3\xa2\xc2\x8c\xc2\x9b', '⌛'.encode('utf-8')),
            (b'\xc3\xa2\xc2\x8c\xc2\x9b', '⌛'.encode('utf-8')),
            # Box-drawing triple-encoded
            (b'\xc3\xa2\xc2\x95\xc2\x94', '╔'.encode('utf-8')),
            (b'\xc3\xa2\xc2\x95\xc2\x90', '═'.encode('utf-8')),
            (b'\xc3\xa2\xc2\x95\xc2\x97', '╗'.encode('utf-8')),
            (b'\xc3\xa2\xc2\x95\xc2\x91', '║'.encode('utf-8')),
            (b'\xc3\xa2\xc2\x95\xc2\xa0', '╠'.encode('utf-8')),
            (b'\xc3\xa2\xc2\x95\xc2\xa3', '╣'.encode('utf-8')),
            (b'\xc3\xa2\xc2\x95\xc2\xa6', '╦'.encode('utf-8')),
            (b'\xc3\xa2\xc2\x95\xc2\xac', '╬'.encode('utf-8')),
            (b'\xc3\xa2\xc2\x95\xc2\xa9', '╩'.encode('utf-8')),
            (b'\xc3\xa2\xc2\x95\xc2\x9a', '╚'.encode('utf-8')),
            # Also common MIS-interpreted ones
            (b'\xe2\x9c\x85', '✅'.encode('utf-8')),
            (b'\xef\xb8\x8f', ''.encode('utf-8')), # Remove VS-16
            (b'\xc2\x81', ''.encode('utf-8')), # Control character artifacts
            (b'\xc2\xa0', ' '.encode('utf-8')), # Non-breaking space
             # MT5 arrow
            (b'\xc3\xa2\xc2\x86\xc2\x92', '→'.encode('utf-8')),
             # Box lines again (alternative common corruption)
            (b'\xc3\xa2\xc2\x94\xc2\xac', '─'.encode('utf-8')),
            (b'\xc3\xa2\xc2\x94\xc2\x82', '│'.encode('utf-8')),
        ]
        
        # New aggressive purge: if we see 'Ã' followed by ANY character that 
        # looks like mojibake, and it's not a valid UTF-8 sequence, then we must clean it.
        # But for now, let's just stick to the specific patterns we've found.
        
        new_data = data
        for old, new in replacements:
            new_data = new_data.replace(old, new)
        
        # Finally, if any byte > 127 remains that isn't valid UTF-8, replace with ASCII equivalent.
        # This is dangerous for a general script, but good for a "purge".
        # We will iterate through and count remaining Ã characters.
        
        if new_data != data:
            with open(file_path, 'wb') as f:
                f.write(new_data)
            print(f"Purged: {file_path}")
            return True
            
    except Exception as e:
        print(f"Error purging {file_path}: {e}")
    return False

def main():
    src_dir = 'src'
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                final_purge(os.path.join(root, file))

if __name__ == "__main__":
    main()
