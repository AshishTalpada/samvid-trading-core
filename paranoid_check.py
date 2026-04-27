import os

# Paranoid check: any byte sequence that looks like common mojibake
MOJIBAKE_MARKERS = [
    b'\xc3\xa2', b'\xc3\xb0', b'\xc2\x81', b'\xc2\xa0', b'\xc2\x9c', b'\xc2\x9d'
]

def paranoid_check():
    src_dir = 'src'
    corrupted = []
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'rb') as f:
                        data = f.read()
                    
                    found = []
                    for marker in MOJIBAKE_MARKERS:
                        if marker in data:
                            found.append(marker.hex())
                    
                    if found:
                        corrupted.append((path, found))
                except:
                    pass
    return corrupted

if __name__ == "__main__":
    results = paranoid_check()
    if not results:
        print("PARANOID CLEAN: No mojibake markers found in any source file!")
    else:
        print(f"FAILED PARANOID CHECK: {len(results)} files still suspected.")
        for path, markers in results:
            print(f"  - {path} (Markers: {', '.join(markers)})")
