#!/usr/bin/env bash
set -Eeuo pipefail

# ---- config ----
DEFAULT_BRANCH="${DEFAULT_BRANCH:-main}"
BASE_URL="${BASE_URL:-https://virtualme2.up.railway.app}"
PR1_BRANCH="chore/version-diagnostics-fix"
PR2_BRANCH="chore/no-store-for-hot-assets-fix"
STASH_NAME="vm-wip-$(date +%s)"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing tool: $1" >&2; exit 1; }; }

echo ">> Preflight"
need git; need gh; need curl
git fetch --all --prune

echo ">> Checkout default branch"
git checkout "${DEFAULT_BRANCH}"
git pull --ff-only

echo ">> Stash working changes"
git stash push -u -m "$STASH_NAME" || true

echo ">> PR1: version endpoint + UI badge + test"
git checkout -B "$PR1_BRANCH" "$DEFAULT_BRANCH"
# bring in only the files we want from the stash
if git rev-parse --verify "stash@{0}" >/dev/null 2>&1; then
  git checkout "stash@{0}" -- routes/status.py static/show_me_window.html tests/test_status_version.py || true
fi

git add routes/status.py static/show_me_window.html tests/test_status_version.py || true
if git diff --cached --quiet; then
  echo "No diffs for PR1; skipping commit"
else
  git commit -m "chore(status): add /status/version and UI badge"
fi

git push -u origin "$PR1_BRANCH"
gh pr create --base "$DEFAULT_BRANCH" --head "$PR1_BRANCH" \
  --title "chore(status): version endpoint + UI badge" \
  --body "Adds GET /status/version (+ UI badge) and unit test for debugging stale assets." || true

PR1_URL="$(gh pr view "$PR1_BRANCH" --json url -q .url || true)"
echo "PR1_URL=$PR1_URL"


echo ">> PR2: no-store for hot assets + tests (+ smoke)"
git checkout -B "$PR2_BRANCH" "$DEFAULT_BRANCH"
if git rev-parse --verify "stash@{0}" >/dev/null 2>&1; then
  git checkout "stash@{0}" -- main.py tests/test_cache_headers.py scripts/smoke_all.sh || true
fi

git add main.py tests/test_cache_headers.py scripts/smoke_all.sh || true
if git diff --cached --quiet; then
  echo "No diffs for PR2; skipping commit"
else
  git commit -m "chore(cache): no-store for hot Show Me assets + tests (+ smoke version)"
fi

git push -u origin "$PR2_BRANCH"
gh pr create --base "$DEFAULT_BRANCH" --head "$PR2_BRANCH" \
  --title "chore(cache): no-store for hot Show Me assets" \
  --body "Sets Cache-Control: no-store for /showme and /static/show_me_window.js; adds tests and smoke hook." || true

PR2_URL="$(gh pr view "$PR2_BRANCH" --json url -q .url || true)"
echo "PR2_URL=$PR2_URL"


echo ">> Drop stash (remaining changes are now covered by PRs)"
git stash drop "stash@{0}" || true

merge_when_green () {
  local pr_branch="$1"
  echo "   waiting for checks on $pr_branch …"
  gh pr checks "$pr_branch" --watch || true
  echo "   merging $pr_branch …"
  gh pr merge "$pr_branch" --squash --delete-branch || true
}

echo ">> Wait & merge PR1"
merge_when_green "$PR1_BRANCH"

echo ">> Wait & merge PR2"
merge_when_green "$PR2_BRANCH"

echo ">> Verify deployed version endpoint and cache headers"
echo "   GET /status/version"
curl -sS "$BASE_URL/status/version" | sed -n '1,8p' || true
echo "   HEAD /showme"
curl -sSI "$BASE_URL/showme" | sed -n '1,20p' || true
echo "   HEAD /static/show_me_window.js"
curl -sSI "$BASE_URL/static/show_me_window.js" | sed -n '1,20p' || true

echo "OK: shipping done."
