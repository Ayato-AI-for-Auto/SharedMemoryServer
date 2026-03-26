import os
import sys
import re
import asyncio
import time
import math
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
from shared_memory.exceptions import SecurityError

# Global flag for structured logging
ENABLE_STRUCTURED_LOGGING = (
    os.environ.get("ENABLE_STRUCTURED_LOGGING", "true").lower() == "true"
)


def log_error(msg: str, e: Exception = None, extra: Dict[str, Any] = None):
    """
    Standard error logger. Supports plain text and structured JSON output.
    """
    if ENABLE_STRUCTURED_LOGGING:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "ERROR",
            "message": msg,
            "exception": str(e) if e else None,
            "extra": extra or {},
        }
        sys.stderr.write(json.dumps(log_entry) + "\n")
    else:
        error_msg = f"[SharedMemoryServer ERROR] {msg}"
        if e:
            error_msg += f": {e}"
        if extra:
            error_msg += f" | {extra}"
        sys.stderr.write(error_msg + "\n")


def log_info(msg: str, extra: Dict[str, Any] = None):
    """
    Standard info logger.
    """
    if ENABLE_STRUCTURED_LOGGING:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "INFO",
            "message": msg,
            "extra": extra or {},
        }
        sys.stdout.write(json.dumps(log_entry) + "\n")
    else:
        info_msg = f"[SharedMemoryServer INFO] {msg}"
        if extra:
            info_msg += f" | {extra}"
        sys.stdout.write(info_msg + "\n")


def get_db_path():
    return os.environ.get("MEMORY_DB_PATH", "shared_memory.db")


def get_thoughts_db_path():
    return os.environ.get("THOUGHTS_DB_PATH", "thoughts.db")


def get_bank_dir():
    return os.environ.get("MEMORY_BANK_DIR", "memory-bank")


def mask_sensitive_data(text: str) -> str:
    if not isinstance(text, str):
        return text

    patterns = [
        (r"AIza[0-9A-Za-z-_]{35}", "[GOOGLE_API_KEY_MASKED]"),
        (r"sk-[a-zA-Z0-9\-]{20,}", "[API_KEY_MASKED]"),
        (r"(password\s*[:=]\s*)([^\s]+)", r"\1[PASSWORD_MASKED]"),
        (
            r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+ PRIVATE KEY-----",
            "[PRIVATE_KEY_MASKED]",
        ),
    ]

    masked_text = text
    for pattern, replacement in patterns:
        masked_text = re.sub(
            pattern,
            replacement,
            masked_text,
            flags=re.IGNORECASE if "password" in pattern else 0,
        )

    return masked_text


def sanitize_filename(filename: str) -> str:
    """
    Expert-level filename sanitization to prevent path traversal and
    illegal characters on any OS.
    """
    if not filename:
        return "unnamed_file.md"

    # Remove any directory components
    name = os.path.basename(filename)

    # Remove non-alphanumeric/dot/underscore/hyphen
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)

    # Force .md extension if missing or incorrect
    if not name.endswith(".md"):
        name = re.sub(r"\.[^.]+$", "", name)  # remove old extension
        name += ".md"

    return name


def safe_path_join(base_dir: str, filename: str) -> str:
    """
    Strict path joining that ensures the resulting path is within the base_dir.
    """
    sanitized = sanitize_filename(filename)
    full_path = os.path.normpath(os.path.join(base_dir, sanitized))

    if not full_path.startswith(os.path.normpath(base_dir)):
        raise SecurityError(f"Path traversal detected: {filename}")

    return full_path


class GlobalLock:
    """
    Expert-level cross-process locking using a lockfile.
    Works by attempting to exclusively create a .lock file.
    """

    def __init__(self, lock_name: str, timeout: float = 10.0):
        self.lock_path = os.path.join(os.getcwd(), f"{lock_name}.lock")
        self.timeout = timeout
        self.locked = False

    async def __aenter__(self):
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            try:
                # Exclusive creation - atomic at OS level
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w") as f:
                    f.write(str(os.getpid()))
                self.locked = True
                return self
            except FileExistsError:
                # Check for stale lock (older than 30s)
                try:
                    mtime = os.path.getmtime(self.lock_path)
                    if time.time() - mtime > 30:
                        os.remove(self.lock_path)
                except FileNotFoundError:
                    pass
                await asyncio.sleep(0.1)

        raise TimeoutError(f"Could not acquire global lock for {self.lock_path}")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.locked:
            # Give the OS a tiny moment to release handles if needed (especially on Windows)
            for _ in range(5):
                try:
                    if os.path.exists(self.lock_path):
                        os.remove(self.lock_path)
                    break
                except PermissionError:
                    await asyncio.sleep(0.05)
                except FileNotFoundError:
                    break
            self.locked = False


def batch_cosine_similarity(
    query_vector: List[float], vectors: List[List[float]]
) -> List[float]:
    """
    Expert-level optimized batch cosine similarity.
    """
    if not vectors:
        return []

    # Pre-calculate query magnitude
    q_mag = math.sqrt(sum(v * v for v in query_vector))
    if q_mag == 0:
        return [0.0] * len(vectors)

    similarities = []
    for v in vectors:
        dot_product = sum(a * b for a, b in zip(query_vector, v))
        v_mag = math.sqrt(sum(x * x for x in v))
        if v_mag == 0:
            similarities.append(0.0)
        else:
            similarities.append(dot_product / (q_mag * v_mag))
    return similarities


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """
    Expert-level single cosine similarity.
    """
    if not v1 or not v2:
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot_product / (mag1 * mag2)


def calculate_importance(access_count: int, last_accessed_iso: str) -> float:
    """
    Calculates a weight based on access frequency and recency.
    """
    # 1. Frequency score (logarithmic to prevent saturation)
    freq_score = math.log1p(access_count) / 10.0  # Normalized roughly

    # 2. Recency score (Exponential decay)
    try:
        last_accessed = datetime.fromisoformat(last_accessed_iso)
        seconds_since = (datetime.now(timezone.utc) - last_accessed).total_seconds()
        # Decay half-life: 24 hours (86400 seconds)
        recency_score = math.exp(-seconds_since / 86400.0)
    except Exception:
        recency_score = 0.5

    return (freq_score * 0.4) + (recency_score * 0.6)
