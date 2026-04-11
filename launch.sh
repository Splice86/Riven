#!/bin/bash
# Riven Launch Script - starts API and CLI

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting Riven API server..."
python api.py &
API_PID=$!

# Wait for API to be ready
echo "Waiting for API..."
for i in {1..30}; do
    if curl -s http://localhost:8080/ > /dev/null 2>&1; then
        echo "API ready!"
        break
    fi
    sleep 0.5
done

# Check if API started
if ! curl -s http://localhost:8080/ > /dev/null 2>&1; then
    echo "Error: API failed to start"
    kill $API_PID 2>/dev/null
    exit 1
fi

# Run CLI
echo "Starting CLI..."
cd cli
python cli.py
CLI_EXIT=$?

# Clean up API on exit
kill $API_PID 2>/dev/null

exit $CLI_EXIT