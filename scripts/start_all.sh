#!/usr/bin/env bash
# Start Radar Data, Radar Builder and Radar Desk (web app on port 8000) in the background.
cd "$(dirname "$0")/.."
PROCS='agents\.data_agent|agents\.builder_agent|uvicorn web\.server'
pkill -f "$PROCS" 2>/dev/null
# an agent busy with a Gemini call can take a while to stop; it must be gone
# before the new one starts, or BAND refuses the new one (agent already running)
for _ in $(seq 1 10); do pgrep -f "$PROCS" >/dev/null || break; sleep 1; done
pkill -9 -f "$PROCS" 2>/dev/null
rm -f /tmp/band-agent-* 2>/dev/null
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
