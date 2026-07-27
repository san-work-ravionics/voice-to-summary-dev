#!/bin/bash
# Double-click this file to start the Voice to Summary local web server.

set -e

# Move to the project root (the directory this script lives in), so it works
# no matter where it's launched from.
cd "$(dirname "$0")"

# Activate the shared virtual environment if it exists.
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

PORT=8743
URL="http://localhost:$PORT/webapp/index.html"

echo "Starting Voice to Summary server..."
echo "Open $URL in your browser (it should open automatically)."
echo "Press Ctrl+C in this window to stop the server."
echo

# Open the browser shortly after the server starts.
( sleep 1.5 && open "$URL" ) &

python3 webapp/server.py "$PORT"
