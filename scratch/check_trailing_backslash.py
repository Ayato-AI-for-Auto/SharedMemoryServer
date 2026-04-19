
import os

files = [
    "src/shared_memory/database.py",
    "src/shared_memory/logic.py",
    "scripts/migrations/manager.py",
    "scripts/migrations/versions/v001_remove_foreign_keys.py",
    "scripts/run_migrations.py"
]

def check_trailing(path):
    if not os.path.exists(path):
        return
    with open(path, "rb") as f:
        content = f.read().decode("utf-8")
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.endswith("\\"):
                # Check for hidden characters in the raw content
                # Wait, splitlines removes \n. 
                pass
        
        # Check raw lines
        f.seek(0)
        raw_lines = f.readlines()
        for i, line in enumerate(raw_lines):
            line_str = line.decode("utf-8")
            if "\\" in line_str:
                idx = line_str.find("\\")
                after = line_str[idx+1:]
                # If after the backslash there is anything other than newline, it's an error.
                if after and after.strip("\r\n"):
                    print(f"ERROR: Found trailing characters after backslash in {path} at line {i+1}: '{line_str.strip()}' (After: {repr(after)})")

if __name__ == "__main__":
    for f in files:
        check_trailing(f)
