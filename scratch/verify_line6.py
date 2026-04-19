
import os
import sys

files_to_check = [
    "src/shared_memory/database.py",
    "src/shared_memory/logic.py",
    "src/shared_memory/server.py",
    "scripts/run_migrations.py",
    "scripts/migrations/manager.py",
    "scripts/migrations/versions/v001_remove_foreign_keys.py",
]

def analyze_line_6(file_path):
    if not os.path.exists(file_path):
        return
    
    print(f"Analyzing {file_path}")
    with open(file_path, "rb") as f:
        lines = f.readlines()
        if len(lines) >= 6:
            line = lines[5] # Line 6 (0-indexed 5)
            print(f"  Line 6 (HEX): {line.hex()}")
            print(f"  Line 6 (REPR): {repr(line)}")
            
            # Check for trailing spaces or other characters after \
            # (Note: This is more generic than just line 6)
            for i, l in enumerate(lines):
                if b"\\" in l:
                    idx = l.find(b"\\")
                    after = l[idx+1:]
                    # strip \r\n
                    clean_after = after.replace(b"\r", b"").replace(b"\n", b"")
                    if clean_after and clean_after.strip(b" ") == b"":
                        print(f"  [!] DANGER: Found space after backslash at line {i+1}: {repr(l)}")
        else:
            print(f"  File only has {len(lines)} lines.")

if __name__ == "__main__":
    for f in files_to_check:
        analyze_line_6(f)
