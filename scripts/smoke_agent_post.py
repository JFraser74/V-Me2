#!/usr/bin/env python3
"""Simple smoke script that starts the FastAPI app and POSTs to /agent/chat.

Usage: python scripts/smoke_agent_post.py

It will print the JSON response from the endpoint. Use this locally for quick
end-to-end verification (requires env vars if you want DB-backed behavior).
"""
import os
import time
import threading
import requests


def _start_server():
    # Start uvicorn programmatically so tests can run against it.
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("main:app", host="127.0.0.1", port=port, log_level="warning")


def main():
    t = threading.Thread(target=_start_server, daemon=True)
    t.start()
    # give the server a moment to start
    time.sleep(1.0)

    port = int(os.getenv("PORT", "8080"))
    url = f"http://127.0.0.1:{port}/agent/chat"
    payload = {"message": "Hello from smoke script"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        print("status:", r.status_code)
        try:
            print(r.json())
        except Exception:
            print(r.text)
    except Exception as e:
        print("Request failed:", e)


if __name__ == "__main__":
    main()
