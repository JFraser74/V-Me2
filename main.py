#!/usr/bin/env python3
# (2025-09-23 16:49 ET - Boot/Deploy Fix - solid)
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="V-Me2")

# CORS (adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional static mount (only if folder exists)
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!doctype html>
    <html>
      <head><meta charset="utf-8"><title>V-Me2</title></head>
      <body style="font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial">
        <h1>V-Me2</h1>
        <p>If you see this, the server is up. Try <a href="/health">/health</a> or <a href="/ui">/ui</a>.</p>
        <ul>
          <li><a href="/ui">/ui</a></li>
          <li><a href="/health">/health</a></li>
        </ul>
      </body>
    </html>
    """

@app.get("/ui")
async def ui():
    return HTMLResponse("""
      <div style="font-family: system-ui; padding: 1rem">
        <h2>V-Me UI (minimal)</h2>
        <p>Next step: connect to <code>/agent/chat</code> once we add it.</p>
        <script src="/static/ui.js"></script>
      </div>
    """)

@app.get("/health")
async def health():
    return PlainTextResponse("ok")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))  # Railway provides PORT
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
