#!/bin/sh
set -e

ollama serve &

until curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; do
  sleep 1
done

cd tasks/task1
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8080}"
