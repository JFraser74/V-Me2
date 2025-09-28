import os
import subprocess
from typing import Optional, Dict, Any, List
from vme_lib.supabase_client import settings_get


def _gh_env():
    env = os.environ.copy()
    tok = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN") or (settings_get("GITHUB_PAT") or "")
    if tok:
        env["GH_TOKEN"] = tok
    return env


def _run(cmd: List[str], timeout: int = 60):
    # NEVER use shell=True; capture output and mask tokens
    p = subprocess.run(cmd, capture_output=True, text=True, env=_gh_env(), timeout=timeout)
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    tok = _gh_env().get("GH_TOKEN", "")
    if tok:
        out = out.replace(tok, "***")
        err = err.replace(tok, "***")
    return p.returncode, out, err


def gh_pr_create(base: str, head: str, title: Optional[str] = None, body: Optional[str] = None):
    # validate branch names minimally
    for s in (base, head):
        if not s or any(c.isspace() for c in s):
            return 400, "", "invalid branch name"
    cmd = ["gh", "pr", "create", "--base", base, "--head", head, "--fill"]
    if title:
        cmd += ["--title", title]
    if body:
        cmd += ["--body", body]
    return _run(cmd)
