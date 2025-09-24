"""Filesystem + Git tools for the agent (safe-by-default)

This module exposes tools suitable for LangGraph/LLM tool calling. Each tool
uses `langchain_core.tools.tool` so they can be registered with the agent.
Write/commit/upsert operations are dry-run unless confirm=True is provided.
"""
from __future__ import annotations
from typing import Optional
from pathlib import Path
import subprocess, shlex
from pydantic import BaseModel
from langchain_core.tools import tool

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _safe_resolve(path: str) -> Path:
    p = (PROJECT_ROOT / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    if not str(p).startswith(str(PROJECT_ROOT)):
        raise ValueError("Path escapes project root")
    return p


class LsArgs(BaseModel):
    path: Optional[str] = "."

@tool("ls", args_schema=LsArgs)
def ls_tool(path: Optional[str] = ".") -> str:
    """List files. Args: path (optional)."""
    try:
        p = _safe_resolve(path or ".")
        if not p.exists():
            return f"Not found: {p}"
        if p.is_file():
            return f"FILE {p.relative_to(PROJECT_ROOT)} size={p.stat().st_size}"
        items = []
        for child in sorted(p.iterdir()):
            kind = "DIR" if child.is_dir() else "FILE"
            items.append(f"{kind}\t{child.relative_to(PROJECT_ROOT)}")
        return "\n".join(items) or "(empty)"
    except Exception as e:
        return f"ls error: {e}"


class ReadArgs(BaseModel):
    path: str
    start: int = 0
    end: int = 200000

@tool("read_file", args_schema=ReadArgs)
def read_file_tool(path: str, start: int = 0, end: int = 200000) -> str:
    """Read a file slice. Args: path, start, end (byte offsets)."""
    try:
        p = _safe_resolve(path)
        if not p.exists() or not p.is_file():
            return f"Not a file: {p}"
        data = p.read_text(errors="replace")
        return data[start:end]
    except Exception as e:
        return f"read_file error: {e}"


class WriteArgs(BaseModel):
    path: str
    content: str
    confirm: bool = False
    create_dirs: bool = True

@tool("write_file", args_schema=WriteArgs)
def write_file_tool(path: str, content: str, confirm: bool = False, create_dirs: bool = True) -> str:
    """Safely write file. Requires confirm=True to persist. Returns diff-style preview on dry-run."""
    try:
        p = _safe_resolve(path)
        if create_dirs:
            p.parent.mkdir(parents=True, exist_ok=True)
        original = ""
        if p.exists():
            try:
                original = p.read_text(errors="replace")
            except Exception:
                original = "(binary or unreadable)"
        if not confirm:
            # Dry-run preview (basic)
            return f"DRY_RUN: would write {len(content)} bytes to {p.relative_to(PROJECT_ROOT)}\nUse confirm=True to persist."
        p.write_text(content)
        return f"WROTE {len(content)} bytes to {p.relative_to(PROJECT_ROOT)}"
    except Exception as e:
        return f"write_file error: {e}"


def _run(cmd: str) -> str:
    try:
        proc = subprocess.run(shlex.split(cmd), cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=30)
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        rc = proc.returncode
        return f"$ {cmd}\n(exit {rc})\n{out}\n{err}"
    except Exception as e:
        return f"exec error: {e}"


@tool("git_status")
def git_status_tool() -> str:
    """Show git status (porcelain + branch)."""
    return _run("git status --porcelain=v1 -b")


@tool("git_diff")
def git_diff_tool() -> str:
    """Show git diff (unstaged)."""
    return _run("git diff")


class CommitArgs(BaseModel):
    message: str
    add_all: bool = True
    confirm: bool = False

@tool("git_commit", args_schema=CommitArgs)
def git_commit_tool(message: str, add_all: bool = True, confirm: bool = False) -> str:
    """Commit changes. Requires confirm=True. Args: message, add_all (default True)."""
    if not confirm:
        return "DRY_RUN: set confirm=True to run git add/commit."
    cmds = []
    if add_all:
        cmds.append("git add -A")
    cmds.append(f"git commit -m {shlex.quote(message)}")
    out = []
    for c in cmds:
        out.append(_run(c))
    return "\n\n".join(out)
