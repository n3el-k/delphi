#!/usr/bin/env bash
# Start everything for local dev in one terminal: the API, the web app and the webhook tunnel.
#
#   ./scripts/start.sh            install what's missing, seed a fresh database, then run it all
#
# Ctrl+C stops everything it started. Output is prefixed [api], [web] or [smee].
# The smee client only starts if SMEE_URL is set in backend/.env and no other client is
# running (two clients deliver every webhook twice).
#
# Settings (optional): API_PORT (default 8000) and WEB_PORT (default 5173).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

die() { echo "start: $*" >&2; exit 1; }
say() { echo "start: $*"; }

# Prefix each line of a command's output so three logs can share one terminal
prefixed() {
  local tag="$1"; shift
  "$@" 2>&1 | awk -v tag="$tag" '{ print tag " " $0; fflush() }'
}

port_in_use() { lsof -iTCP:"$1" -sTCP:LISTEN -n -P >/dev/null 2>&1; }

# Stop with a message that says what holds the port and how to free it
check_port() {
  local port="$1" what="$2" pids
  port_in_use "$port" || return 0
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN | sort -u | tr '\n' ' ')"
  echo "start: port $port is already in use, probably by an old $what. Nothing was started." >&2
  ps -o pid=,command= -p "${pids// /,}" 2>/dev/null | cut -c1-120 | sed 's/^/start:   /' >&2
  echo "start: stop it (Ctrl+C in its terminal, or: kill ${pids% }) and run this again." >&2
  exit 1
}

# 1. Tools
command -v uv >/dev/null || die "uv is not installed. See https://docs.astral.sh/uv/"
command -v npm >/dev/null || die "npm is not installed. You need Node 20+."

# 2. Secrets: never create a real .env with values, only copy the template
if [ ! -f "$ROOT/backend/.env" ]; then
  cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
  die "created backend/.env from .env.example. Fill it in (see the README), then run this again."
fi

# 3. Ports: a second copy of the API would fight the first over the database
check_port "$API_PORT" "API"
check_port "$WEB_PORT" "web app"

# 4. Dependencies (uv sync is a no-op when nothing changed; npm install only when needed)
say "checking backend dependencies"
(cd "$ROOT/backend" && uv sync --quiet)
if [ ! -d "$ROOT/frontend/node_modules" ] || [ "$ROOT/frontend/package-lock.json" -nt "$ROOT/frontend/node_modules/.package-lock.json" ]; then
  say "installing frontend dependencies"
  (cd "$ROOT/frontend" && npm install --no-fund --no-audit)
fi

# 5. Database: seed only if there isn't one, so restarting keeps your projects.
#    After a models.py change, run: (cd backend && uv run python -m app.seed)
if [ ! -f "$ROOT/backend/app.db" ]; then
  say "no database yet, seeding the demo learner"
  (cd "$ROOT/backend" && uv run python -m app.seed)
fi

# 6. Run. On exit (Ctrl+C or one side crashing the script), stop the whole process group.
trap 'trap - INT TERM EXIT; echo; say "stopping"; kill 0 2>/dev/null' INT TERM EXIT

# On a non-default port, point CORS (FRONTEND_ORIGIN) and the web app (VITE_API_URL) at
# each other. Environment variables win over the .env files. Default ports leave them alone.
[ "$WEB_PORT" = 5173 ] || export FRONTEND_ORIGIN="http://localhost:$WEB_PORT"
[ "$API_PORT" = 8000 ] || export VITE_API_URL="http://localhost:$API_PORT"

prefixed "[api] " bash -c "cd '$ROOT/backend' && exec uv run fastapi dev app/main.py --port $API_PORT" &
prefixed "[web] " bash -c "cd '$ROOT/frontend' && exec npm run dev -- --port $WEB_PORT --strictPort" &

SMEE_URL="$(grep -E '^SMEE_URL=' "$ROOT/backend/.env" | cut -d= -f2- || true)"
if [ -z "$SMEE_URL" ]; then
  say "SMEE_URL is empty in backend/.env, so GitHub webhooks won't reach this laptop"
elif pgrep -f smee-client >/dev/null; then
  say "a smee client is already running, so not starting another (two would double every webhook)"
else
  prefixed "[smee]" npx -y smee-client --url "$SMEE_URL" --target "http://localhost:$API_PORT/webhooks/github" &
fi

say "API on http://localhost:$API_PORT (docs at /docs), app on http://localhost:$WEB_PORT. Ctrl+C to stop."
wait
