from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pathlib import Path

router = APIRouter(prefix="/status", tags=["status"])


@router.get("/goals", response_class=HTMLResponse)
def goals():
    p = Path("static/goals.html")
    if not p.exists():
        return HTMLResponse("<h1>Goals</h1><p>No table available yet.</p>", status_code=200)
    return HTMLResponse(p.read_text(encoding="utf-8"))
