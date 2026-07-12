#!/usr/bin/env bash
#
# Run the test suite for the ApacheCon 2022 IoT demo.
#
# The test service is profile-gated (profiles: [test]) so it does not start
# with the normal `docker compose up`. This script activates that profile and
# runs the pytest suite inside a container that shares the compose network,
# so it can reach the Zenoh broker and IoTDB.
#
# Usage:
#   ./scripts/test.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "==> Running test suite (pytest) ..."
docker compose --profile test run --rm test

echo
echo "==> Tests complete."
