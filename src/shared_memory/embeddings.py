import os
import hashlib
import json
import sqlite3
from typing import List, Optional
from google import genai
from shared_memory.utils import log_error, log_info
from shared_memory.database import get_connection

EMBEDDING_MODEL = "gemini-embedding-001"
DIMENSIONALITY = 768


def _get_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _get_cached_embedding(text_hash: str) -> Optional[List[float]]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT vector FROM embedding_cache WHERE content_hash = ? AND model_name = ?",
            (text_hash, EMBEDDING_MODEL),
        ).fetchone()
        if row:
            return json.loads(row[0].decode("utf-8"))
    except sqlite3.Error as e:
        log_error("Failed to read from embedding cache", e)
    finally:
        conn.close()
    return None


def _save_to_cache(text_hash: str, vector: List[float]):
    conn = get_connection()
    try:
        vector_json = json.dumps(vector).encode("utf-8")
        conn.execute(
            "INSERT OR REPLACE INTO embedding_cache (content_hash, vector, model_name) VALUES (?, ?, ?)",
            (text_hash, vector_json, EMBEDDING_MODEL),
        )
        conn.commit()
    except sqlite3.Error as e:
        log_error("Failed to save to embedding cache", e)
    finally:
        conn.close()


def get_gemini_client() -> Optional[genai.Client]:
    """
    Retrieves a Gemini API client using the best available API key.
    Prioritizes:
    1. Environment variables (GOOGLE_API_KEY or GEMINI_API_KEY)
    2. .env file
    3. Global settings.json (SharedMemoryServer specific env)
    4. Global settings.json (fallback)
    """
    source = "None"
    # 1. Check environment variables directly
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if api_key:
        source = "Environment Variable"

    # 2. Try loading from .env if still missing
    if not api_key:
        try:
            from dotenv import load_dotenv

            load_dotenv()
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            if api_key:
                source = ".env file"
        except ImportError:
            pass

    # 3. Try loading from global settings.json
    if not api_key:
        global_settings_path = os.path.expanduser("~/.gemini/settings.json")
        if os.path.exists(global_settings_path):
            try:
                with open(global_settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)

                    # Targeted: settings.json -> mcpServers -> SharedMemoryServer -> env
                    mcp_env = (
                        settings.get("mcpServers", {})
                        .get("SharedMemoryServer", {})
                        .get("env", {})
                    )
                    api_key = mcp_env.get("GOOGLE_API_KEY") or mcp_env.get(
                        "GEMINI_API_KEY"
                    )
                    if api_key:
                        source = "settings.json (mcpServers.SharedMemoryServer.env)"

                    # Fallback: Top-level or any occurrence
                    if not api_key:
                        api_key = settings.get("GOOGLE_API_KEY") or settings.get(
                            "GEMINI_API_KEY"
                        )
                        if api_key:
                            source = "settings.json (global)"
            except Exception as e:
                log_error(f"Failed to read settings from {global_settings_path}", e)

    if not api_key:
        return None

    # DIAGNOSTIC LOG: Write to a PHYSICAL file for analysis (Temporary)
    masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
    with open("KEY_DIAG_LOG.txt", "w", encoding="utf-8") as f:
        f.write(f"Source: {source}\n")
        f.write(f"Key Masked: {masked_key}\n")
        f.write(f"Key Length: {len(api_key)}\n")
        f.write(f"Full Env GOOGLE: {repr(os.environ.get('GOOGLE_API_KEY'))}\n")
        f.write(f"Full Env GEMINI: {repr(os.environ.get('GEMINI_API_KEY'))}\n")

    try:
        return genai.Client(api_key=api_key.strip())
    except Exception as e:
        log_error("Failed to initialize Gemini client", e)
        return None


async def compute_embedding(text: str) -> Optional[List[float]]:
    """Computes embedding with local caching."""
    text_hash = _get_text_hash(text)
    cached = _get_cached_embedding(text_hash)
    if cached:
        return cached

    client = get_gemini_client()
    if not client:
        return None

    try:
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config={"output_dimensionality": DIMENSIONALITY},
        )
        vector = result.embeddings[0].values
        _save_to_cache(text_hash, vector)
        return vector
    except Exception as e:
        log_error("Embedding computation failed", e)
        return None


async def compute_embeddings_bulk(texts: List[str]) -> List[Optional[List[float]]]:
    """Computes multiple embeddings efficiently."""
    if not texts:
        return []

    results = [None] * len(texts)
    to_fetch_indices = []
    to_fetch_texts = []

    for i, text in enumerate(texts):
        text_hash = _get_text_hash(text)
        cached = _get_cached_embedding(text_hash)
        if cached:
            results[i] = cached
        else:
            to_fetch_indices.append(i)
            to_fetch_texts.append(text)

    if not to_fetch_texts:
        return results

    client = get_gemini_client()
    if not client:
        return results

    try:
        batch_result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=to_fetch_texts,
            config={"output_dimensionality": DIMENSIONALITY},
        )

        for i, emb in enumerate(batch_result.embeddings):
            original_idx = to_fetch_indices[i]
            vector = emb.values
            results[original_idx] = vector
            _save_to_cache(_get_text_hash(to_fetch_texts[i]), vector)
    except Exception as e:
        log_error("Bulk embedding computation failed", e)

    return results
