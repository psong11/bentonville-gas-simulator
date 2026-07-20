#!/usr/bin/env bash
# Assemble and deploy the FastAPI backend to Vercel (project: gas-sim-api).
#
# Why a staging dir: Vercel auto-builds every file under api/ as a serverless
# function, but our FastAPI package IS named api/. Staging nests the real code
# under server/ and exposes a single shim entry at api/index.py.
#
# Usage: scripts/deploy_backend.sh [--prod]
set -euo pipefail
cd "$(dirname "$0")/.."

STAGE=".vercel_backend"
rm -rf "$STAGE"
mkdir -p "$STAGE/api" "$STAGE/server/api" "$STAGE/server/data"

# backend source
cp physics.py risk.py placement.py city_gen.py leak_detector.py "$STAGE/server/"
cp api/*.py "$STAGE/server/api/"
cp data/network.json data/leak_signatures.npz "$STAGE/server/data/"
cp requirements.txt "$STAGE/requirements.txt"

# single function entry
cat > "$STAGE/api/index.py" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from api.main import app  # noqa: E402,F401  (ASGI app served by @vercel/python)
PY

cat > "$STAGE/vercel.json" <<'JSON'
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "functions": {
    "api/index.py": {
      "includeFiles": "server/**"
    }
  },
  "rewrites": [{ "source": "/(.*)", "destination": "/api/index" }]
}
JSON

# preserve the project link across rebuilds
if [ -d ".vercel_backend_link" ]; then
  cp -R .vercel_backend_link "$STAGE/.vercel"
fi

cd "$STAGE"
vercel deploy ${1:-} --yes 2>&1 | tail -5
cd ..

# save the link created on first deploy
if [ -d "$STAGE/.vercel" ]; then
  rm -rf .vercel_backend_link
  cp -R "$STAGE/.vercel" .vercel_backend_link
fi
