import hashlib
import json
import os

from google import genai

from shared_memory.config import settings
from shared_memory.database import async_get_connection, retry_on_db_lock
from shared_memory.utils import get_logger, log_error

logger = get_logger("embeddings")

EMBEDDING_MODEL = "models/text-embedding-004"


def _get_text_hash(text: str) -> str:
    """Returns MD5 hash of the text for caching."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def get_gemini_client():
    """
    Returns a Gemini API client using the key from config or environment.
    """
    api_key = os.environ.get("GOOGLE_API_KEY") or settings.api_key
    if not api_key:
        logger.warning("GOOGLE_API_KEY not found in environment or config.")
        return None
    return genai.Client(api_key=api_key)


async def compute_embeddings_bulk(texts: list[str]) -> list[list[float]]:
    """
    Computes embeddings for a list of strings.
    Alias for compute_embedding to maintain backward compatibility with graph.py.
    """
    return await compute_embedding(texts)


@retry_on_db_lock()
async def compute_embedding(text_list: list[str]) -> list[list[float]]:
    """
    Computes text embeddings using the Gemini API (Async).
    Uses a local SQLite cache to avoid redundant API calls.
    """
    client = get_gemini_client()
    if not client:
        return [([0.0] * 768) for _ in text_list]

    # 1. Filter out empty strings
    valid_entries = []
    for i, txt in enumerate(text_list):
        if txt and txt.strip():
            # Truncate extremely long texts
            valid_entries.append((i, txt[:10000]))

    if not valid_entries:
        return [([0.0] * 768) for _ in text_list]

    # 2. Check cache
    results = [None] * len(text_list)
    to_compute = []
    compute_map = []

    async with await async_get_connection() as conn:
        for original_idx, txt in valid_entries:
            content_hash = _get_text_hash(txt)
            cursor = await conn.execute(
                "SELECT vector FROM embedding_cache WHERE content_hash = ?",
                (content_hash,),
            )
            row = await cursor.fetchone()
            if row:
                results[original_idx] = json.loads(row[0])
            else:
                to_compute.append(txt)
                compute_map.append((original_idx, content_hash))

    if not to_compute:
        return [r if r is not None else ([0.0] * 768) for r in results]

    # 3. Compute missing embeddings via Async API
    try:
        response = await client.aio.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=to_compute,
            config={"task_type": "RETRIEVAL_DOCUMENT"},
        )

        async with await async_get_connection() as conn:
            for idx, (original_idx, content_hash) in enumerate(compute_map):
                vector = response.embeddings[idx].values
                results[original_idx] = vector

                # Update cache
                await conn.execute(
                    """
                    INSERT OR REPLACE INTO embedding_cache
                    (content_hash, vector, model_name)
                    VALUES (?, ?, ?)
                """,
                    (content_hash, json.dumps(vector), EMBEDDING_MODEL),
                )
            await conn.commit()

    except Exception as e:
        log_error("Failed to compute embeddings via Gemini API", e)
        # Fallback
        for original_idx, _ in compute_map:
            results[original_idx] = [0.0] * 768

    # Ensure all slots are filled
    return [r if r is not None else ([0.0] * 768) for r in results]
