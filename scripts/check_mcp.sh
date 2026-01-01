#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${1:-"https://workout-tracker-mcp-3tbf7k4y5a-uc.a.run.app/mcp"}
PAYLOAD_FILE=${2:-""}

if [[ -n "$PAYLOAD_FILE" && ! -f "$PAYLOAD_FILE" ]]; then
  echo "Payload file not found: $PAYLOAD_FILE" >&2
  exit 1
fi

TMP_HEADERS=$(mktemp)
trap 'rm -f "$TMP_HEADERS"' EXIT

# Get a session id from response headers (expect 400 with header).
curl -s -D "$TMP_HEADERS" -o /dev/null -H "Accept: text/event-stream" "$BASE_URL"
SESSION_ID=$(awk 'BEGIN{IGNORECASE=1} /^mcp-session-id:/ {print $2}' "$TMP_HEADERS" | tr -d '\r')

if [[ -z "$SESSION_ID" ]]; then
  echo "Failed to obtain mcp-session-id from server." >&2
  exit 1
fi

echo "Session: $SESSION_ID"

# Open SSE stream in background
curl -s -N -H "Accept: text/event-stream" -H "mcp-session-id: $SESSION_ID" "$BASE_URL" &
SSE_PID=$!

sleep 1

# Initialize
curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"script","version":"0.0.1"},"capabilities":{}}}'

# List tools
curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# Optionally call add_workout_entry with provided payload file
if [[ -n "$PAYLOAD_FILE" ]]; then
  PAYLOAD_JSON=$(cat "$PAYLOAD_FILE")
  curl -s -X POST "$BASE_URL" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "mcp-session-id: $SESSION_ID" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"add_workout_entry\",\"arguments\":$PAYLOAD_JSON}}"
fi

# Let SSE stream print a bit then stop
sleep 2
kill "$SSE_PID" >/dev/null 2>&1 || true
