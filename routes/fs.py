from __future__ import annotations
from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
from typing import Optional
from vme_lib import supabase_client as sbmod

# We’ll reuse the existing tools implementation for safe pathing and git.
try:
    from tools.codespace import (
        ls_tool, read_file_tool, write_file_tool,
        git_status_tool, git_diff_tool, git_commit_tool
    )
except Exception:
    ls_tool = read_file_tool = write_file_tool = None
    git_status_tool = git_diff_tool = git_commit_tool = None

router = APIRouter(prefix="/fs", tags=["fs"])

def require_tools():
    if not all([ls_tool, read_file_tool, write_file_tool, git_status_tool, git_diff_tool, git_commit_tool]):
        raise HTTPException(status_code=503, detail="Codespace tools not available")


@router.get("/ls")
def ls(path: str = Query(".", description="Path relative to project root")):
    require_tools()
    return {"ok": True, "result": ls_tool.invoke({"path": path})}


class ReadIn(BaseModel):
    path: str
    start: int = 0
    end: int = 200000


@router.post("/read")
def read(payload: ReadIn):
    require_tools()
    return {"ok": True, "result": read_file_tool.invoke(payload.dict())}


class WriteIn(BaseModel):
    path: str
    content: str
    confirm: bool = False
    create_dirs: bool = True


@router.post("/write")
def write(payload: WriteIn, x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    # Require admin token for confirm writes
    from os import getenv
    # Support admin token from env or from va_settings so the UI can manage it.
    admin = getenv("SETTINGS_ADMIN_TOKEN") or sbmod.settings_get('SETTINGS_ADMIN_TOKEN')
    if payload.confirm and (not admin or x_admin_token != admin):
        raise HTTPException(status_code=403, detail="Admin token required for confirm=True")
    require_tools()
    return {"ok": True, "result": write_file_tool.invoke(payload.dict())}


@router.get("/git/status")
def git_status():
    require_tools()
    return {"ok": True, "result": git_status_tool.invoke({})}


@router.get("/git/diff")
def git_diff():
    require_tools()
    return {"ok": True, "result": git_diff_tool.invoke({})}


class CommitIn(BaseModel):
    message: str
    add_all: bool = True
    confirm: bool = False


@router.post("/git/commit")
def git_commit(payload: CommitIn, x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    from os import getenv
    admin = getenv("SETTINGS_ADMIN_TOKEN") or sbmod.settings_get('SETTINGS_ADMIN_TOKEN')
    if payload.confirm and (not admin or x_admin_token != admin):
        raise HTTPException(status_code=403, detail="Admin token required for confirm=True")
    require_tools()
    return {"ok": True, "result": git_commit_tool.invoke(payload.dict())}
