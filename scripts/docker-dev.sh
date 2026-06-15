#!/usr/bin/env sh
set -eu
python scripts/embedding_server.py --host 0.0.0.0 --port 8010 &
exec docker compose up -d --build elasticsearch redis api frontend
