import os
import json
from google import genai
from typing import Optional

def check_key():
    settings_path = os.path.expanduser("~/.gemini/settings.json")
    print(f"[DEBUG] Settings path: {settings_path}")
    
    env_google = os.environ.get("GOOGLE_API_KEY")
    env_gemini = os.environ.get("GEMINI_API_KEY")
    print(f"[DEBUG] Environ GOOGLE_API_KEY: {repr(env_google)}")
    print(f"[DEBUG] Environ GEMINI_API_KEY: {repr(env_gemini)}")

    if os.path.exists(settings_path):
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
            # Targeted path search
            mcp_env = (
                settings.get("mcpServers", {})
                .get("SharedMemoryServer", {})
                .get("env", {})
            )
            key = mcp_env.get("GOOGLE_API_KEY") or mcp_env.get("GEMINI_API_KEY")
            
            if key:
                print(f"[DEBUG] Key found in settings.json: {repr(key)}")
                print(f"[DEBUG] Key Length: {len(key)}")
                
                # Test initializing client with this key
                try:
                    client = genai.Client(api_key=key.strip())
                    print("[DEBUG] Client initialized successfully (dry run)")
                    
                    # Try a very simple API call to see if the key is REJECTED by the server
                    # client.models.list() is a good test.
                    print("[DEBUG] Attempting to list models...")
                    models = list(client.models.list())
                    print(f"[DEBUG] Successfully listed {len(models)} models.")
                except Exception as e:
                    print(f"[ERROR] API test failed: {e}")
            else:
                print("[DEBUG] Key NOT found in settings.json")
    else:
        print(f"[ERROR] {settings_path} does not exist")

if __name__ == "__main__":
    check_key()
