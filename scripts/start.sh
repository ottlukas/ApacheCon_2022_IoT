#!/usr/bin/env bash
#
# Start the ApacheCon 2022 IoT demo stack.
#
# This script brings up the full Docker Compose stack:
#   - Zenoh broker
#   - Apache IoTDB 2.0.x (persistent time-series storage)
#   - Zenoh-to-IoTDB bridge
#   - Panel dashboard (served via Panel/HoloViz on port 5006)
#   - Simulator (publishes telemetry to Zenoh)
#
# Usage:
#   ./scripts/start.sh           # build (if needed) and start detached
#   ./scripts/start.sh --no-build # start without rebuilding images
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

BUILD_ARGS=()
if [[ "${1:-}" == "--no-build" ]]; then
  BUILD_ARGS=(--no-build)
fi

echo "==> Starting ApacheCon 2022 IoT stack (Panel dashboard, no NGINX) ..."
docker compose up -d --build "${BUILD_ARGS[@]}"

echo
echo "==> Waiting for services to become healthy ..."
# Give IoTDB's healthcheck a moment; depends_on already orders startup.
sleep 5

echo
echo "==> Stack status:"
docker compose ps

echo
echo "==> Dashboard available at: http://localhost:5006/panel"
echo "==> Zenoh REST API at:       http://localhost:8000"
echo "==> IoTDB Thrift RPC at:     localhost:6667"
