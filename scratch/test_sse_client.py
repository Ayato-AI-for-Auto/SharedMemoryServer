
import requests
import json
import time
import threading
import re

def listen_sse():
    print("Connecting to SSE...")
    response = requests.get("http://localhost:8377/sse", stream=True)
    print(f"SSE Status: {response.status_code}")
    
    session_id = None
    for line in response.iter_lines():
        if line:
            text = line.decode()
            print(f"SSE: {text}")
            if "session_id=" in text:
                match = re.search(r"session_id=([a-f0-9]+)", text)
                if match:
                    session_id = match.group(1)
                    print(f"DETECTED Session ID: {session_id}")
                    # Trigger POST in a separate call
                    send_init(session_id)

def send_init(session_id):
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "1.0",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"}
        }
    }
    print(f"Sending InitializeRequest for {session_id}...")
    resp = requests.post(f"http://localhost:8377/messages/?session_id={session_id}", json=init_req)
    print(f"POST Status: {resp.status_code}")
    print(f"POST Response: {resp.text}")

# Start SSE listener
listen_sse()
