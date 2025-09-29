from fastapi import APIRouter, HTTPException
from pathlib import Path
import json

router = APIRouter(prefix="/status", tags=["status"])

DATA_PATH = Path(__file__).resolve().parents[1] / "config" / "goals.json"


@router.get("/goals")
def list_goals():
    if not DATA_PATH.exists():
        raise HTTPException(status_code=404, detail="goals.json missing")
    try:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("expected list")
        return {"items": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"bad goals.json: {e}")
