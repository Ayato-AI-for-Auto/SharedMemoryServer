import asyncio
import logging
import math
import os
import re
import sys
import random
import time
from datetime import UTC, datetime
from functools import wraps

from loguru import logger as loguru_logger

from shared_memory.exceptions import SecurityError

# Global flag for structured logging (defined in config)
_STRUCTURED_LOGGING = False


def set_structured_logging(enabled: bool):
    global _STRUCTURED_LOGGING
    _STRUCTURED_LOGGING = enabled


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger configured for the SharedMemoryServer.
    Encapsulates standard library logging setup.
    """
    logger = logging.getLogger(f"shared_memory.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log_info(msg: str):
    """Abstraction for logging info messages."""
    get_logger("core").info(msg)


def log_error(msg: str, error: Exception | None = None):
    """Abstraction for logging error messages with optional exception details."""
    logger = get_logger("core")
    if error:
        logger.error(f"{msg}: {error}", exc_info=True)
    else:
        logger.error(msg)


def get_db_path() -> str:
    """
    Returns the absolute path to the knowledge database.
    Prioritizes MEMORY_DB_PATH env var, then SHARED_MEMORY_HOME.
    """
    db_path = os.environ.get("MEMORY_DB_PATH")
    if db_path:
        return os.path.abspath(db_path)

    home = os.environ.get("SHARED_MEMORY_HOME", "data")
    return os.path.abspath(os.path.join(home, "knowledge.db"))


def get_thoughts_db_path() -> str:
    """Returns the absolute path to the thoughts database."""
    db_path = os.environ.get("THOUGHTS_DB_PATH")
    if db_path:
        return os.path.abspath(db_path)

    home = os.environ.get("SHARED_MEMORY_HOME", "data")
    return os.path.abspath(os.path.join(home, "thoughts.db"))


def get_bank_dir() -> str:
    """Returns the absolute path to the memory bank directory."""
    bank_dir = os.environ.get("MEMORY_BANK_DIR")
    if bank_dir:
        return os.path.abspath(bank_dir)

    home = os.environ.get("SHARED_MEMORY_HOME", "data")
    return os.path.abspath(os.path.join(home, "bank"))


def calculate_similarity(v1: list[float], v2: list[float]) -> float:
    """
    Calculates cosine similarity between two vectors.
    Returns 0.0 if vectors are empty or have different lengths.
    """
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(v1, v2, strict=True))
    norm_v1 = math.sqrt(sum(a * a for a in v1))
    norm_v2 = math.sqrt(sum(a * a for a in v2))

    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0

    return dot_product / (norm_v1 * norm_v2)


def batch_cosine_similarity(query_vector: list[float], vectors: list[list[float]]) -> list[float]:
    """
    Computes cosine similarity between a query vector and a list of vectors.
    """
    return [calculate_similarity(query_vector, v) for v in vectors]


def security_scan(content: str):
    """
    Placeholder for basic security scanning of content.
    Prevents potential prompt injection or malformed data issues.
    """
    if not content:
        return

    # Advanced security logic would go here
    # For now, we just ensure it's a string
    if not isinstance(content, str):
        raise SecurityError("Non-string content detected in security scan.")


def clean_markdown(text: str) -> str:
    """
    Strips dangerous or unnecessary markdown elements from distilled content.
    """
    if not text:
        return ""
    # Simple regex to strip code blocks backticks if they wrap the whole thing
    text = re.sub(r"^```markdown\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip()


class PathResolver:
    """Utility to resolve standard data paths."""

    @staticmethod
    def get_base_data_dir() -> str:
        home = os.environ.get("SHARED_MEMORY_HOME")
        if home:
            return os.path.abspath(home)
        return os.path.abspath("data")


# Intra-process Global Locks
_GLOBAL_LOCKS: dict[str, asyncio.Lock] = {}


class GlobalLock:
    """
    Provides a named, intra-process lock (asyncio.Lock).
    Used to prevent race conditions during file or database access
    within the same event loop.
    """

    def __init__(self, name: str):
        self.name = name
        if name not in _GLOBAL_LOCKS:
            _GLOBAL_LOCKS[name] = asyncio.Lock()
        self._lock = _GLOBAL_LOCKS[name]

    async def __aenter__(self):
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._lock.release()

    @property
    def file_locked(self) -> bool:
        return self._lock.locked()


def sanitize_filename(name: str) -> str:
    """
    Converts a string into a safe filename.
    Removes path traversal attempts and special characters.
    """
    # 0. Strip directories and spaces
    name = os.path.basename(name).strip()

    # 1. Strip ANY existing extension (e.g., .txt, .md) to enforce .md
    name, _ = os.path.splitext(name)
    name = name.strip()

    # 2. Replace anything not alphanumeric or underscore/hyphen/dot
    clean = re.sub(r"[^\w\-\.]", "_", name.lower())
    # Collapse multiple underscores
    clean = re.sub(r"_+", "_", clean)

    # 3. Prevent hidden files or path traversal
    clean = clean.lstrip(".")
    if not clean:
        clean = "unnamed_entity"

    return f"{clean}.md"


def mask_sensitive_data(text: str) -> str:
    """
    Masks sensitive information like API keys in logs or content.
    Identifies patterns like 'AIza...' (Google API keys) and 'sk-...' (Generic keys).
    """
    if not text:
        return ""
    # Mask Google API Key pattern
    text = re.sub(r"AIzaSy[a-zA-Z0-9\-_]{33}", "[GOOGLE_API_KEY_MASKED]", text)
    # Mask Generic/OpenAI API Key pattern
    text = re.sub(r"sk-[a-zA-Z0-9]{20,}", "[API_KEY_MASKED]", text)
    # Mask Email addresses
    text = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL_MASKED]", text)
    return text


def safe_path_join(base_dir: str, filename: str) -> str:
    """
    Safely joins a base directory with a filename, ensuring
    the resulting path is within the base directory.
    Prevents path traversal attacks.
    """
    base_dir = os.path.abspath(base_dir)
    filename = os.path.basename(filename)  # Only keep the last part
    joined = os.path.abspath(os.path.join(base_dir, filename))

    if not joined.startswith(base_dir):
        raise ValueError(f"Dangerous path detected: {joined}")

    return joined


def calculate_importance(access_count: int, last_accessed: str) -> float:
    """
    Calculates the importance score of a piece of knowledge based on
    access frequency and recency (time decay).
    """
    try:
        # 1. Base score from frequency (logarithmic scaling)
        freq_score = math.log1p(access_count)

        # 2. Time decay (Exponential decay)
        # Assuming last_accessed is an ISO timestamp
        last_dt = datetime.fromisoformat(last_accessed.replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=UTC)

        now = datetime.now(UTC)
        days_ago = (now - last_dt).total_seconds() / (24 * 3600)

        # Decay constant: half-life of 30 days
        decay = math.exp(-days_ago / 30.0)

        return freq_score * decay
    except Exception as e:
        log_error(
            f"Importance calculation failed for count={access_count}, last={last_accessed}", e
        )
        return 0.0


def parse_retry_delay(error: Exception) -> float | None:
    """
    Parses the retry delay from a Gemini API error.
    Handles both string messages and structured error details.
    """
    error_str = str(error)

    # 1. Try regex on the string message (e.g., "Please retry in 41.359s")
    match = re.search(r"retry in ([\d.]+)s", error_str)
    if match:
        return float(match.group(1))

    # 2. Try to extract from ClientError details if available (google-genai specific)
    try:
        # ClientError.message often contains the JSON-like representation
        if hasattr(error, "message") and isinstance(error.message, dict):
            details = error.message.get("error", {}).get("details", [])
            for detail in details:
                if detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                    delay_str = detail.get("retryDelay", "0s")
                    return float(delay_str.rstrip("s"))
    except Exception:
        pass

    return None


def retry_on_ai_quota(max_retries: int = 3, initial_backoff: float = 2.0):
    """
    Decorator for retrying AI API calls on 429 RESOURCE_EXHAUSTED errors.
    Supports exponential backoff with jitter and respects retryDelay from API.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    e_str = str(e).upper()
                    if "429" in e_str or "RESOURCE_EXHAUSTED" in e_str:
                        if attempt == max_retries:
                            loguru_logger.error(
                                f"AI Quota exhausted after {max_retries} retries: {e}"
                            )
                            raise

                        # Determine wait time
                        retry_delay = parse_retry_delay(e)
                        if retry_delay:
                            wait_time = retry_delay + random.uniform(0, 1.0)
                        else:
                            wait_time = (initial_backoff * (2**attempt)) + random.uniform(0, 1.0)

                        loguru_logger.warning(
                            f"AI Quota Exceeded (429). Attempt {attempt + 1}/{max_retries}. "
                            f"Retrying in {wait_time:.2f}s..."
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        # Not a quota error, re-raise immediately
                        raise

            raise last_error

        return wrapper

    return decorator


class AIRateLimiter:
    """
    Centralized rate limiter for AI API calls (Gemini).
    Specifically designed to handle Free Tier '429 RESOURCE_EXHAUSTED' errors.
    """

    _last_call_times: dict[str, float] = {}
    _locks: dict[str, asyncio.Lock] = {}

    # Default intervals (Free Tier: 10 RPM -> 6s, Embeddings: 1500 RPM -> ~0.04s but 1s is safer)
    GENERATION_INTERVAL = 6.0
    EMBEDDING_INTERVAL = 1.0

    @classmethod
    async def throttle(cls, task_type: str = "generation"):
        """
        Enforces a minimum time interval between AI calls based on task type.
        Usage: await AIRateLimiter.throttle("generation")
        """
        interval = (
            cls.GENERATION_INTERVAL if task_type == "generation" else cls.EMBEDDING_INTERVAL
        )

        if task_type not in cls._locks:
            cls._locks[task_type] = asyncio.Lock()

        async with cls._locks[task_type]:
            now = asyncio.get_event_loop().time()
            last_time = cls._last_call_times.get(task_type, 0.0)
            elapsed = now - last_time

            if elapsed < interval:
                wait_time = interval - elapsed
                loguru_logger.debug(
                    f"AI Quota Throttling ({task_type}): Waiting {wait_time:.2f}s..."
                )
                await asyncio.sleep(wait_time)
                cls._last_call_times[task_type] = asyncio.get_event_loop().time()
            else:
                cls._last_call_times[task_type] = now

    @classmethod
    def set_interval(cls, task_type: str, seconds: float):
        if task_type == "generation":
            cls.GENERATION_INTERVAL = seconds
        else:
            cls.EMBEDDING_INTERVAL = seconds
