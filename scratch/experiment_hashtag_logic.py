import asyncio
import json
import time
import re
import os
from collections import Counter
from typing import List

# Import real client if available, otherwise mock
try:
    from shared_memory.infra.embeddings import get_gemini_client
    from shared_memory.common.config import settings
    from shared_memory.core.ai_control import AIRateLimiter
    REAL_AI = True
except ImportError:
    REAL_AI = False

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "when", "at", "by", "for", "with",
    "is", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "i", "you", "he", "she", "it", "we", "they", "my", "your", "his", "her", "its", "our", "their",
    "this", "that", "these", "those", "which", "who", "whom", "whose", "where", "how", "why",
    "can", "could", "shall", "should", "will", "would", "may", "might", "must",
    "in", "on", "to", "from", "up", "down", "out", "of", "about", "above", "below", "between",
    "currently", "named", "using", "through", "during", "actually", "basically", "simply"
}

def extract_hashtags_logic(content: str, max_tags: int = 5) -> List[str]:
    if not content: return []
    words = re.findall(r'\w+', content.lower())
    filtered = [w for w in words if len(w) > 3 and w not in STOP_WORDS and not w.isdigit()]
    counts = Counter(filtered)
    return [f"#{word}" for word, _ in counts.most_common(max_tags)]

async def extract_hashtags_ai(content: str) -> List[str]:
    if not REAL_AI:
        await asyncio.sleep(0.5)
        return ["#mock_ai_tag"]
    
    try:
        client = get_gemini_client()
        if not client: return ["#error_no_client"]
        
        prompt = (
            "Extract up to 5 highly relevant hashtags from the text. "
            "Output MUST be a JSON list of strings.\n\n"
            f"TEXT: {content}"
        )
        await AIRateLimiter.throttle()
        response = await client.aio.models.generate_content(
            model=settings.generative_model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        return json.loads(response.text)
    except Exception as e:
        return [f"#error_{type(e).__name__}"]

async def run_experiment():
    test_cases = [
        ("Short", "The capital of France is Paris."),
        ("Medium", "User is currently working on a project named SharedMemoryServer using Python and MCP."),
        ("Long", "The SharedMemoryServer is a memory management system for agentic workflows. It uses SQLite for persistence and Gemini for semantic search and knowledge distillation. It aims to provide a long-term memory for LLM agents to maintain context across sessions."),
        ("Technical", "Implementing EDINET API v2 with iXBRL parsing for Japanese financial statements.")
    ]
    
    print(f"{'Type':<10} | {'Method':<10} | {'Tags':<40} | {'Time'}")
    print("-" * 80)
    
    for label, text in test_cases:
        # Logic
        s1 = time.perf_counter()
        t_logic = extract_hashtags_logic(text)
        d1 = time.perf_counter() - s1
        print(f"{label:<10} | Logic      | {str(t_logic):<40} | {d1:.5f}s")
        
        # AI
        s2 = time.perf_counter()
        t_ai = await extract_hashtags_ai(text)
        d2 = time.perf_counter() - s2
        print(f"{'':<10} | AI         | {str(t_ai):<40} | {d2:.5f}s")
        print("-" * 80)

if __name__ == "__main__":
    asyncio.run(run_experiment())
