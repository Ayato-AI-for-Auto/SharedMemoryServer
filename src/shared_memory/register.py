import os
import json
import sys
import argparse
from pathlib import Path

def get_config_paths():
    """Detect potential MCP configuration file paths on Windows."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return {}

    return {
        "Claude Desktop": Path(appdata) / "Claude" / "claude_desktop_config.json",
        "Cursor (Roo Code/Cline)": Path(appdata) / "Cursor" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
        "Antigravity (Roo Code/Cline)": Path(appdata) / "antigravity" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
        "Antigravity (Central)": Path("C:/Users/saiha/.gemini/antigravity/mcp_config.json"),
        "Cursor (Global)": Path(appdata) / "Cursor" / "User" / "settings.json"
    }

def get_server_command():
    """Get the absolute command to run the server."""
    # Assuming 'uv' is used and the project is installed in editable mode
    # The command should ideally use the full path to the python executable in .venv
    cwd = os.getcwd()
    venv_python = os.path.join(cwd, ".venv", "Scripts", "python.exe")
    server_script = os.path.join(cwd, "src", "shared_memory", "server.py")
    
    if not os.path.exists(venv_python):
        # Fallback to current sys.executable if .venv not found
        venv_python = sys.executable

    return [venv_python, server_script]

def register_mcp(dry_run=False):
    paths = get_config_paths()
    cmd = get_server_command()
    
    mcp_config = {
        "command": cmd[0],
        "args": cmd[1:],
        "env": {
            "MEMORY_DB_PATH": os.path.join(os.getcwd(), "shared_memory.db"),
            "MEMORY_BANK_DIR": os.path.join(os.getcwd(), "memory-bank")
        }
    }

    print(f"Target Command: {' '.join(cmd)}")
    print("-" * 30)

    for name, path in paths.items():
        if not path.parent.exists():
            continue

        print(f"Checking {name}: {path}")
        
        config = {}
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception as e:
                print(f"  [ERROR] Failed to read {path}: {e}")
                continue

        # Determine where to put the MCP config based on file type
        if any(x in str(path) for x in ["mcp_config.json", "cline_mcp_settings.json", "claude_desktop_config.json"]):
            if "mcpServers" not in config:
                config["mcpServers"] = {}
            config["mcpServers"]["SharedMemoryServer"] = mcp_config
        elif "settings.json" in str(path):
            # For Cursor global settings, it might be under 'cursor.cpp.mcpServers' or similar
            # But usually, it's safer to let the user do this or target specific extensions
            print(f"  [SKIP] Global Cursor settings.json is complex. Please register manually via UI if needed.")
            continue

        if dry_run:
            print(f"  [DRY RUN] Would update: {path}")
            # print(json.dumps(config, indent=2)) # Too noisy
        else:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)
                print(f"  [SUCCESS] Updated {path}")
            except Exception as e:
                print(f"  [ERROR] Failed to write {path}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Register SharedMemoryServer as an MCP tool.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes.")
    args = parser.parse_args()
    
    register_mcp(dry_run=args.dry_run)

if __name__ == "__main__":
    main()
