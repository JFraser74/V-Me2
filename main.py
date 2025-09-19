from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

# Serve static files (e.g., logo, UI.js)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h1>V-Me2 Main UI - Show-Me Window</h1><p>Voice: Hey assistant</p><select><option>Email</option><option>Coding</option><option>Supabase</option></select>"

@app.get("/ui")
async def ui():
    return "<div>Show-Me UI: Modes dropdown</div>"

@app.get("/voice_chat")
async def voice_chat():
    return {"message": "Voice chat active"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
