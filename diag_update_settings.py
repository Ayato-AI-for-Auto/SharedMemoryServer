import os
import json
from pathlib import Path

def update_settings():
    settings_path = os.path.expanduser("~/.gemini/settings.json")
    if not os.path.exists(settings_path):
        print(f"Error: {settings_path} not found")
        return

    with open(settings_path, "r", encoding="utf-8") as f:
        settings = json.load(f)

    # Targeted: settings.json -> mcpServers -> SharedMemoryServer -> env
    try:
        sm_env = settings["mcpServers"]["SharedMemoryServer"]["env"]
        # Clear/Update PYTHONPATH to point to the current edit directory
        cwd = os.getcwd().replace("\\", "/")
        src_path = f"{cwd}/src"
        sm_env["PYTHONPATH"] = f"{src_path};{sm_env.get('PYTHONPATH', '')}"
        print(f"Updated PYTHONPATH to: {sm_env['PYTHONPATH']}")
        
        # Save back
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        print("Settings updated successfully.")
    except KeyError as e:
        print(f"Error: MCP configuration not found in settings.json: {e}")

if __name__ == "__main__":
    update_settings()
