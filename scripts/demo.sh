#!/usr/bin/env bash
# The live GitHub loop in three commands, so nobody types git on stage.
#
#   ./scripts/demo.sh start <ticket id>   open a PR with the eval() flaw for that ticket
#   ./scripts/demo.sh fix                 push the fix to that PR
#   ./scripts/demo.sh reset               close demo PRs, delete their branches, reseed the database
#
# The demo repo has two fixed branches that this script never changes:
#   feat/evaluate-expression  the calculator with eval() on user input (code injection)
#   demo/evaluate-fix         the same plus the 2-commit fix (parse, don't run; a length cap)
# Each run gets its own throwaway branch, live/run-1, live/run-2, ...
#
# Settings (optional): DEMO_DIR is your clone of the demo repo (default ../level1-calculator
# next to this repo), DEMO_REPO is its GitHub name (default n3el-k/level1-calculator).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO_DIR="${DEMO_DIR:-$ROOT/../level1-calculator}"
DEMO_REPO="${DEMO_REPO:-n3el-k/level1-calculator}"
FLAW_BRANCH="feat/evaluate-expression"
FIX_BRANCH="demo/evaluate-fix"
PREFIX="live/run-"

die() { echo "demo: $*" >&2; exit 1; }
demo_git() { git -C "$DEMO_DIR" "$@"; }

check_clone() {
  [ -d "$DEMO_DIR/.git" ] || die "no clone of $DEMO_REPO at $DEMO_DIR. Clone it there, or set DEMO_DIR."
  # Switching branches would carry stray edits into the demo PR
  if ! demo_git diff --quiet || ! demo_git diff --cached --quiet; then
    die "$DEMO_DIR has uncommitted changes. Commit or discard them first."
  fi
}

start() {
  local ticket="${1:-}"
  [[ "$ticket" =~ ^[0-9]+$ ]] || die "usage: demo.sh start <ticket id>   (the number on the dashboard, e.g. 1)"
  check_clone
  demo_git fetch --quiet --prune origin

  # The next run number nobody has used, locally or on GitHub
  local n=1
  while demo_git show-ref --quiet "refs/heads/$PREFIX$n" || demo_git show-ref --quiet "refs/remotes/origin/$PREFIX$n"; do
    n=$((n + 1))
  done
  local branch="$PREFIX$n"

  demo_git switch --quiet --no-track -c "$branch" "origin/$FLAW_BRANCH"
  demo_git push --quiet -u origin "$branch"
  gh pr create -R "$DEMO_REPO" --head "$branch" --base main \
    --title "Evaluate a whole expression" --body "Ticket: #$ticket"
  echo "The bot reviews it in about 30 seconds. Once the gate says to fix the security finding, run: ./scripts/demo.sh fix"
}

fix() {
  check_clone
  local branch
  branch="$(demo_git branch --show-current)"
  [[ "$branch" == "$PREFIX"* ]] || die "the clone is on '$branch', not a demo branch. Run ./scripts/demo.sh start <ticket id> first."
  demo_git fetch --quiet origin
  demo_git merge --quiet --ff-only "origin/$FIX_BRANCH"
  demo_git push --quiet
  echo "Pushed the fix to $branch. The gate page updates by itself in about 45 seconds."
}

reset() {
  check_clone
  demo_git fetch --quiet --prune origin

  # 1. Close open demo PRs
  local pr
  for pr in $(gh pr list -R "$DEMO_REPO" --state open --json number,headRefName \
    --jq ".[] | select(.headRefName | startswith(\"$PREFIX\")) | .number"); do
    gh pr close "$pr" -R "$DEMO_REPO" >/dev/null 2>&1
    echo "Closed PR #$pr"
  done

  # 2. Delete the run branches on GitHub (a closed PR keeps a "Restore branch" button) and locally
  demo_git switch --quiet main
  local ref
  for ref in $(demo_git for-each-ref --format='%(refname:lstrip=3)' "refs/remotes/origin/$PREFIX*"); do
    demo_git push --quiet origin --delete "$ref"
    echo "Deleted branch $ref on GitHub"
  done
  for ref in $(demo_git for-each-ref --format='%(refname:lstrip=2)' "refs/heads/$PREFIX*"); do
    demo_git branch --quiet -D "$ref"
  done

  # 3. Wipe the database back to the demo learner with no projects
  (cd "$ROOT/backend" && uv run python -m app.seed)
  echo "Reset done. Reload the app: it should say 'No project yet'."
}

case "${1:-help}" in
  start) shift; start "$@" ;;
  fix) fix ;;
  reset) reset ;;
  *) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
