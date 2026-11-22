#!/bin/sh
if [ "${SEED_DEMO:-false}" = true ]; then
    python scripts/seed_demo.py || echo 'Demo seed failed. See trace above.' >&2
fi
exec uvicorn src.main:app --host 0.0.0.0 --port 8000
