#!/bin/bash
# Double-click this file to start the Voice to Summary web server via Docker.

set -e

# Move to the project root (the directory this script lives in), so it works
# no matter where it's launched from.
cd "$(dirname "$0")"

if ! docker info >/dev/null 2>&1; then
  echo "Docker doesn't seem to be running. Start Docker Desktop and try again." >&2
  exit 1
fi

PORT="${PORT:-8743}"
URL="http://localhost:$PORT/webapp/index.html"

echo "Starting Voice to Summary server (Docker)..."
echo "First run downloads/builds the image and can take a few minutes;"
echo "later runs are fast. Open $URL in your browser (it should open"
echo "automatically once the server is ready)."
echo "Press Ctrl+C in this window to stop the server."
echo

# Open the browser once the container reports healthy, instead of guessing
# a fixed delay — the first build/model-download can take a while.
(
  for _ in $(seq 1 300); do
    if curl -s -o /dev/null "http://localhost:$PORT/healthz"; then
      open "$URL"
      break
    fi
    sleep 1
  done
) &

docker compose up --build
