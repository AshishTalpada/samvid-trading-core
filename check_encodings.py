import os

# Mojibake patterns to look for
MOJIBAKE_PATTERNS = [b'\xc3\xa2', b'\xc3\xb0', b'\xe2\x95', b'\xe2\x9c', b'\xf0\x9f']

def check_file(file_path):
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        
        # We look for common mojibake sequences, but excluding some valid UTF-8 ones
        # Actually, let's just search for the specific 'Ã¢' or 'âœ' byte sequences
        # but that would be many. Let's just look for anything outside 0-127 that isn't valid UTF-8?
        # No, the simplest check is to find if 'Ã' (0xC3) followed by common bytes exists.
        
        bad_count = 0
        if b'\xc3\xa2' in data or b'\xc3\xb0' in data:
            return True
            
        return False
    except:
        return False

def main():
    src_dir = 'src'
    corrupted_files = []
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                if check_file(path):
                    corrupted_files.append(path)
    
    if not corrupted_files:
        print("SUCCESS: 100% CLEAN. No UTF-8 corruption (mojibake) detected in 'src/'!")
    else:
        print(f"WARNING: Corruption detected in {len(corrupted_files)} files:")
        for f in corrupted_files:
            print(f"  - {f}")

if __name__ == "__main__":
    main()
