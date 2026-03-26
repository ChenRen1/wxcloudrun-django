#!/usr/bin/env bash

set -euo pipefail

PORT="${PORT:-8010}"

exec ./.venv/bin/python -m uvicorn app.src.wecom.demo_app:app --host 0.0.0.0 --port "${PORT}"
