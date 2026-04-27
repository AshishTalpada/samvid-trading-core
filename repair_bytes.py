import os

def repair_bytes(file_path):
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        
        # Define byte-level replacements for mojibake
        # These are common misinterpretations of UTF-8 as ISO-8859-1/Win-1252
        replacements = [
            # Triple-encoded UTF-8 Emoji Patterns
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
            (b'\xc3\xb0\xc2\x9f\xc2\x9a\xc2\xa8', '🚨'.encode('utf-8')),
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
            # Catch-all for basic UTF-1252 mis-decodings
            (b'\xc3\xa2\xc2\x9c\xc2\x85', '✅'.encode('utf-8')),
            # Standard encoded icons
            (b'\xe2\x9c\x85', '✅'.encode('utf-8')),
            (b'\xf0\x9f\x9a\x80', '🚀'.encode('utf-8')),
        ]
        
        new_data = data
        for old, new in replacements:
            new_data = new_data.replace(old, new)
        
        if new_data != data:
            with open(file_path, 'wb') as f:
                f.write(new_data)
            print(f"Byte-repaired: {file_path}")
            return True
    except Exception as e:
        print(f"Failed byte-repair for {file_path}: {e}")
    return False

def main():
    src_dir = 'src'
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                repair_bytes(os.path.join(root, file))

if __name__ == "__main__":
    main()
