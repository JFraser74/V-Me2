from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from datetime import datetime, timezone
import os, subprocess

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


def _git_short_sha() -> str:
    sha = os.getenv("GIT_COMMIT", "").strip()
    if sha:
        return sha[:8]
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


@router.get("/version")
def version():
    return {
        "commit": _git_short_sha(),
        "build_time": os.getenv("BUILD_TIME", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        "branch": os.getenv("GIT_BRANCH", os.getenv("RAILWAY_GIT_BRANCH", "")),
        "service": "v-me2",
    }
