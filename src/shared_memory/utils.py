import os
import sys
import re

def log_error(msg: str, e: Exception = None):
    error_msg = f"[SharedMemoryServer ERROR] {msg}"
    if e:
        error_msg += f": {e}"
    sys.stderr.write(error_msg + "\n")

def get_db_path():
    return os.environ.get("MEMORY_DB_PATH", "shared_memory.db")

def get_bank_dir():
    return os.environ.get("MEMORY_BANK_DIR", "memory-bank")

def mask_sensitive_data(text: str) -> str:
    if not isinstance(text, str):
        return text
    
    patterns = [
        (r"(AIza[0-9A-Za-z-_]{35})", "[GOOGLE_API_KEY_MASKED]"),
        (r"(sk-[a-zA-Z0-9]{20,})", "[API_KEY_MASKED]"),
        (r"(password\s*[:=]\s*)([^\s]+)", r"\1[PASSWORD_MASKED]"),
        (r"(-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+ PRIVATE KEY-----)", "[PRIVATE_KEY_MASKED]")
    ]
    
    masked_text = text
    for pattern, replacement in patterns:
        masked_text = re.sub(pattern, replacement, masked_text, flags=re.IGNORECASE if "password" in pattern else 0)
    
    return masked_text
