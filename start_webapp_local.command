#!/bin/bash
# Double-click this file to start the Voice to Summary web server LOCALLY
# (no Docker) on port 8744, using the project's .venv.
#
# Use this for fast UI iteration: unlike the Docker launcher, webapp/ files
# are read straight from disk, so edits to app.js/style.css/index.html show
# up on a browser refresh with no rebuild. It runs on a DIFFERENT port (8744)
# than the Docker container (8743) on purpose, so both can run at once and
# you can compare.

set -e

# Move to the project root (the directory this script lives in), so it works
# no matter where it's launched from.
cd "$(dirname "$0")"

PORT="${PORT:-8744}"
URL="http://localhost:$PORT/webapp/index.html"

VENV="${VENV:-$(dirname "$0")/../py-shared-env/dev}"
if [ ! -x "$VENV/bin/python" ]; then
  echo "No venv found at $VENV" >&2
  echo "Set VENV to the path of your Python virtual environment." >&2
  exit 1
fi

# Free the port if a previous local run is still holding it, so re-launching
# doesn't fail with "Address already in use".
if lsof -ti "tcp:$PORT" >/dev/null 2>&1; then
  echo "Port $PORT is in use — stopping the previous local server..."
  lsof -ti "tcp:$PORT" | xargs kill 2>/dev/null || true
  sleep 1
fi

echo "Starting Voice to Summary server (LOCAL, no Docker) on port $PORT..."
echo "Serving webapp/ straight from disk — edit app.js/style.css and just"
echo "refresh the browser. Open $URL (it should open automatically once ready)."
echo "Press Ctrl+C in this window to stop the server."
echo

# Open the browser once the server answers, instead of guessing a fixed delay.
(
  for _ in $(seq 1 60); do
    if curl -s -o /dev/null "http://localhost:$PORT/healthz"; then
      open "$URL"
      break
    fi
    sleep 0.5
  done
) &

exec "$VENV/bin/python" webapp/server.py "$PORT"
