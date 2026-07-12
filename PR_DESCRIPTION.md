# Pull Request: Replace NGINX frontend with Panel (HoloViz) dashboard

## Summary

Removed the NGINX-based frontend and now serve the monitoring UI directly with **Panel (HoloViz)**. No reverse proxy remains in the stack.

## Changes

- **Removed NGINX**: deleted `Dockerfile.frontend` and the `frontend` service from `docker-compose.yml`.
- **Panel dashboard**: renamed `dashboard` → `panel-dashboard`, exposed the Panel UI on **port 5006** (container-internal 8080). Added a `curl /health` healthcheck and `depends_on` ordering.
- **Apache IoTDB 2.0.x**: upgraded image to `apache/iotdb:2.0.10-standalone`. Added `dn_rpc_address=0.0.0.0` so other containers can reach the RPC listener (the image default `127.0.0.1` refuses external connections).
- **Zenoh broker fix**: the listen endpoint had a literal `tcp/[IP_ADDRESS]:7447` placeholder that crashed the broker; changed to `tcp/0.0.0.0:7447`.
- **Simulator fix**: `ZENOH_HOST_ENDPOINT` default changed from `tcp/localhost:7447` to `tcp/zenoh:7447` so the simulator container reaches the broker.
- **Test service restored**: re-added the profile-gated `test` service (uses `Dockerfile.test`).
- **Helper scripts**: `scripts/start.sh`, `scripts/test.sh`, `scripts/stop.sh`.
- **README**: updated for the NGINX removal, Panel on `:5006`, and IoTDB 2.0.x.

## Verification (clean rebuild from scratch)

- `docker compose up --build -d` → all 5 services healthy (`zenoh-broker`, `iotdb-db` 2.0.10, `zenoh-iotdb-bridge`, `panel-dashboard`, `iot-simulator`).
- `curl http://localhost:5006/health` → `{"status":"ok","zenoh_connected":true,"iotdb_connected":true}`.
- Simulator → Zenoh → bridge → IoTDB pipeline verified; timeseries `root.myfactory.machine1.temperature` present with persisted records.
- Panel UI: `/` → 307 redirect, `/panel` → 200 rendering `bokeh` + `echarts`.
- Test suite: `16 passed, 15 skipped`.
