#!/usr/bin/env bash
#
# Stop the ApacheCon 2022 IoT demo stack.
#
# Usage:
#   ./scripts/stop.sh           # stop containers, keep volumes (data persists)
#   ./scripts/stop.sh --clean   # also remove named volumes (DELETES all data)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

if [[ "${1:-}" == "--clean" ]]; then
  echo "==> Stopping stack and removing volumes (ALL IoTDB data will be lost) ..."
  docker compose down -v
else
  echo "==> Stopping stack (volumes preserved) ..."
  docker compose down
fi

echo "==> Done."
