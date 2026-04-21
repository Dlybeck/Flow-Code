#!/bin/bash
# Wrapper so we can see exactly what Claude Code is doing when it spawns us.
LOG=/tmp/flowcode-mcp-launch.log
{
  echo "=== $(date -Iseconds) spawn attempt ==="
  echo "pwd: $(pwd)"
  echo "args: $@"
  echo "PATH: $PATH"
  echo "PYTHONPATH: $PYTHONPATH"
} >> "$LOG" 2>&1

exec "/home/dlybeck/Projects/Modular Code/experiments/3d-layered/.venv/bin/python" \
  "/home/dlybeck/Projects/Modular Code/experiments/3d-layered/sidecar/mcp_server.py" \
  "$@" \
  2>> "$LOG"
