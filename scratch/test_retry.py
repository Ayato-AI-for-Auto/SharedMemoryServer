import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

# Add src to path
import os
sys.path.append(os.path.join(os.getcwd(), "src"))

from shared_memory.utils import retry_on_ai_quota, parse_retry_delay

# Mock error classes
class ClientError(Exception):
    def __init__(self, message, details=None):
        self.message = message
        self.details = details
        super().__init__(str(message))

async def test_retry_logic():
    print("Testing retry_on_ai_quota...")
    
    call_count = 0
    
    @retry_on_ai_quota(max_retries=2, initial_backoff=0.1)
    async def mock_api_call():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            # Mock 429 error
            raise Exception("429 RESOURCE_EXHAUSTED: Please retry in 0.5s")
        return "Success"

    start_time = asyncio.get_event_loop().time()
    result = await mock_api_call()
    end_time = asyncio.get_event_loop().time()
    
    print(f"Result: {result}")
    print(f"Total calls: {call_count}")
    print(f"Duration: {end_time - start_time:.2f}s")
    
    assert result == "Success"
    assert call_count == 3
    print("Test passed!")

async def test_parse_retry_delay():
    print("Testing parse_retry_delay...")
    
    # Case 1: String message
    e1 = Exception("429 RESOURCE_EXHAUSTED: Please retry in 41.359s")
    delay1 = parse_retry_delay(e1)
    print(f"Delay 1: {delay1}")
    assert delay1 == 41.359
    
    # Case 2: Structured message (dict-like)
    # The ClientError in google-genai has a message that might be a dict or string
    mock_error = MagicMock()
    mock_error.message = {
        "error": {
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": "15s"
                }
            ]
        }
    }
    mock_error.__str__.return_value = "Mocked Error"
    
    delay2 = parse_retry_delay(mock_error)
    print(f"Delay 2: {delay2}")
    assert delay2 == 15.0
    
    print("Test passed!")

if __name__ == "__main__":
    asyncio.run(test_retry_logic())
    asyncio.run(test_parse_retry_delay())
