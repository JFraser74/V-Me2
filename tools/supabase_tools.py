"""Supabase data tools (safe-by-default)

These expose `sb_select` and `sb_upsert` as LangChain-style tools. They
return DRY_RUN messages for writes unless confirm=True.
"""
from __future__ import annotations
import json
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from langchain_core.tools import tool
from lib import supabase_client as _sbmod


def _sb():
    try:
        return _sbmod._client()
    except Exception:
        return None


class SelectArgs(BaseModel):
    table: str
    limit: int = 5
    order: Optional[str] = None  # column asc|desc e.g. "created_at desc"

@tool("sb_select", args_schema=SelectArgs)
def sb_select_tool(table: str, limit: int = 5, order: Optional[str] = None) -> str:
    """Select rows from a table. Args: table, limit, order (e.g., 'created_at desc')."""
    sb = _sb()
    if not sb:
        return "Supabase client not configured. Set SUPABASE_URL and key."
    try:
        q = sb.table(table).select("*")
        if order:
            parts = order.split()
            col = parts[0]
            desc = len(parts) > 1 and parts[1].lower().startswith("desc")
            q = q.order(col, desc=desc)
        q = q.limit(limit)
        res = q.execute()
        return json.dumps(res.data or [], default=str)[:200000]
    except Exception as e:
        return f"sb_select error: {e}"


class UpsertArgs(BaseModel):
    table: str
    rows: List[Dict[str, Any]]
    on_conflict: Optional[str] = None
    confirm: bool = False

@tool("sb_upsert", args_schema=UpsertArgs)
def sb_upsert_tool(table: str, rows: List[Dict[str, Any]], on_conflict: Optional[str] = None, confirm: bool = False) -> str:
    """Upsert rows into a table. Requires confirm=True. Args: table, rows, on_conflict (pk/unique col)."""
    if not confirm:
        return f"DRY_RUN: would upsert {len(rows)} row(s) into {table}. Set confirm=True to persist."
    sb = _sb()
    if not sb:
        return "Supabase client not configured. Set SUPABASE_URL and key."
    try:
        q = sb.table(table).upsert(rows)
        if on_conflict:
            q = q.on_conflict(on_conflict)
        res = q.execute()
        return json.dumps(res.data or {"ok": True}, default=str)[:200000]
    except Exception as e:
        return f"sb_upsert error: {e}"
