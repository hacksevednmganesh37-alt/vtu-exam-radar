#!/usr/bin/env bash
# Start Radar Data, Radar Builder and Radar Desk (web app on port 8000) in the background.
cd "$(dirname "$0")/.."
pkill -f 'agents\.data_agent|agents\.builder_agent|uvicorn web\.server' 2>/dev/null
sleep 1
nohup uv run python -m agents.data_agent > /tmp/data.log 2>&1 &
nohup uv run python -m agents.builder_agent > /tmp/builder.log 2>&1 &
nohup uv run uvicorn web.server:app --host 0.0.0.0 --port 8000 > /tmp/desk.log 2>&1 &
sleep 6
if [ -n "$CODESPACE_NAME" ]; then
  gh codespace ports visibility 8000:public -c "$CODESPACE_NAME" >/dev/null 2>&1 || true
  echo "Web app: https://${CODESPACE_NAME}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
fi
grep -h "Agent started" /tmp/data.log /tmp/builder.log
grep -h "Uvicorn running" /tmp/desk.log
echo "Logs: /tmp/data.log /tmp/builder.log /tmp/desk.log"
