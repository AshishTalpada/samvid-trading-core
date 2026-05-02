import os

# Mapping of corrupted byte sequences (encoded as cp1252) to correct UTF-8 strings
REPLACEMENTS = {
    b"\xe2\x9a\xa0\xef\xb8\x8f": "⚠️",  # ⚠️ (Warning)
    b"\xe2\x9a\xa0": "⚠️",  # ⚠️
    b"\xe2\x9c\x85": "✅",  # ✅ (Checkmate)
    b"\xe2\x9c\x94": "✅",  # ✅
    b"\xe2\x9c\x96": "❌",  # ❌ (Cross)
    b"\xe2\x9d\x8c": "❌",  # ❌
    b"\xe2\x9c\x97": "✖",  # ✖
    b"\xe2\x80\x94": "—",  # — (Em-dash)
}


def pest_control_encoding(dir_path):
    print(f"Pest Control: Sanitizing aesthetics in {dir_path}")
    for root, _dirs, files in os.walk(dir_path):
        if any(x in root for x in [".git", ".gemini", "venv", "__pycache__"]):
            continue
        for file in files:
            if file.endswith((".py", ".md", ".txt", ".sh", ".ps1")):
                path = os.path.join(root, file)
                try:
                    with open(path, "rb") as f:
                        raw = f.read()

                    if not raw:
                        continue

                    # 1. Start with raw UTF-8 decode
                    try:
                        content = raw.decode("utf-8")
                        changed = False

                        # Fix misrendered "â" sequences that were accidentally escaped/converted
                        # Common pattern: "❌" might be stored as "â \u008c" or similar
                        misrendered = {
                            "⚠️": "⚠️",
                            "✅": "✅",
                            "❌": "❌",
                            "✖": "✖",
                            "—": "—",
                        }

                        for old, fixed in misrendered.items():
                            if old in content:
                                content = content.replace(old, fixed)
                                changed = True

                        if changed:
                            with open(path, "w", encoding="utf-8", newline="\n") as f:
                                f.write(content)
                            print(f"  ✓ Sanity restored: {path}")

                    except UnicodeDecodeError:
                        # 2. Fallback to repair corrupted bytes directly
                        print(f"  ! Attempting binary repair for non-UTF8: {path}")
                        # We'll try to find the sequences in the raw bytes
                        # This works if the file was saved as cp1252 but contains these symbols
                        # Actually many 'â' things in cp1252 are exactly the same bytes as UTF-8
                        # But misinterpreted.
                        try:
                            content_cp = raw.decode("cp1252")
                            # Now that it's decoded AS if it was cp1252, the "❌" becomes string chars
                            fixed_cp = content_cp
                            misrendered_cp = {
                                "â\u0161\u00a0\u00ef\u00b8\u008f": "⚠️",
                                "â\u0153\u0085": "✅",
                                "â\u009d\u008c": "❌",
                                "â\u0153\x97": "✖",
                            }
                            cp_changed = False
                            for o, f in misrendered_cp.items():
                                if o in fixed_cp:
                                    fixed_cp = fixed_cp.replace(o, f)
                                    cp_changed = True

                            if cp_changed:
                                with open(path, "w", encoding="utf-8", newline="\n") as f:
                                    f.write(fixed_cp)
                                print(f"  ✓ Binary repair success: {path}")
                        except:
                            pass

                except Exception as e:
                    print(f"  ✖ Failed to process {file}: {e}")


if __name__ == "__main__":
    project_root = r"c:\Users\talpa\Desktop\System_Beta\TradingSystem"
    pest_control_encoding(project_root)
    print("Pest Control: Aesthetics Sanity established.")
