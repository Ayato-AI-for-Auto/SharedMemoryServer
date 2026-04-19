
import os

def check_file(path):
    print(f"Checking {path}...")
    with open(path, 'rb') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            # Find the last backslash in the line
            idx = line.rfind(b'\\')
            if idx != -1:
                # Check what comes after it
                after = line[idx+1:]
                # Ignore common escape sequences if they are inside a string?
                # Actually, the error is specifically about LINE CONTINUATION.
                # A line continuation backslash MUST be the last non-newline character.
                
                # Strip \r \n
                clean_after = after.replace(b'\r', b'').replace(b'\n', b'')
                if clean_after:
                    # If it's not empty, it might be a syntax error IF it's intended as line continuation.
                    # Or it might be a space.
                    if clean_after.strip(b' ') == b'':
                        print(f"  [!!!] TRAILING SPACE after backslash at line {i+1}: {repr(line)}")

if __name__ == "__main__":
    src_dir = "src/shared_memory"
    for f in os.listdir(src_dir):
        if f.endswith(".py"):
            check_file(os.path.join(src_dir, f))
