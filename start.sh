#!/usr/bin/env bash
# Start the Kargo Hiring Agent web app.
# Copy .env.example → .env and fill in your keys first.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f .env ]; then
  set -a; source .env; set +a
fi

PORT="${PORT:-5050}"
echo ""
echo "  Kargo Hiring Agent  →  http://localhost:$PORT"
echo ""
exec python3 src/app.py
