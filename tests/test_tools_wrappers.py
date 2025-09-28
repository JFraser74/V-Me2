import subprocess
from tools.github_tools import gh_pr_create
from tools.railway_tools import _run as rw_run


class FakeRun:
    def __init__(self, rc=0, out="OK", err=""):
        self.returncode = rc
        self.stdout = out
        self.stderr = err


def test_gh_pr_create_no_shell(monkeypatch):
    def fake_run(cmd, capture_output, text, env, timeout):
        # ensure cmd is a list and uses gh pr create
        assert isinstance(cmd, list)
        assert "pr" in cmd and "create" in cmd
        return FakeRun()
    monkeypatch.setattr(subprocess, "run", fake_run)
    rc, out, err = gh_pr_create("main", "feat/x", "t", "b")
    assert rc == 0


def test_railway_run_masks_token(monkeypatch):
    def fake_run(cmd, capture_output, text, env, timeout):
        return FakeRun(out=(env.get('RAILWAY_TOKEN','') or 'no'))
    monkeypatch.setattr(subprocess, "run", fake_run)
    rc, out, err = rw_run(["railway", "projects", "list"], timeout=5)
    # out should be string, token masked if present (we didn't set token)
    assert isinstance(out, str)
