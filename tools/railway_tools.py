import os
import subprocess
from typing import Dict, Any, List
from vme_lib.supabase_client import settings_get


def _rw_env():
    env = os.environ.copy()
    tok = os.getenv("RAILWAY_TOKEN") or (settings_get("RAILWAY_TOKEN") or "")
    if tok:
        env["RAILWAY_TOKEN"] = tok
    return env


def _run(cmd: List[str], timeout: int = 60):
    p = subprocess.run(cmd, capture_output=True, text=True, env=_rw_env(), timeout=timeout)
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    tok = _rw_env().get("RAILWAY_TOKEN", "")
    if tok:
        out = out.replace(tok, "***")
        err = err.replace(tok, "***")
    return p.returncode, out, err


def railway_deploy(project_id: str | None = None, service_name: str | None = None):
    cmd = ["railway", "up"]
    if project_id:
        cmd += ["--project", project_id]
    if service_name:
        cmd += ["--service", service_name]
    return _run(cmd, timeout=600)


def list_projects_cli() -> Dict[str, Any]:
    return _run(["railway", "projects", "list"]) if True else (1, "", "disabled")
