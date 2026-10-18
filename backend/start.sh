#!/usr/bin/env bash
set -e

python -m blackbox.seed --all
exec uvicorn blackbox.api:app --host 0.0.0.0 --port "${PORT:-10000}"
