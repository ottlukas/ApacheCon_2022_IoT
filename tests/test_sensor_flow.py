# -*- coding: utf-8 -*-
"""Integration tests for the end-to-end sensor simulator data flow.

The pipeline under test:

    Sensor Simulator (scripts/sensor_simulator.py)
        -> Zenoh Broker (tcp/zenoh:7447 or tcp/localhost:7447)
        -> Zenoh Bridge (bridge/zenoh_to_iotdb.py)
        -> IoTDB (root.myfactory.machine1.temperature)
        -> Panel Diagrams (app/dashboard.py)

Two layers of test are provided:

1. ``test_simulator_api_*`` -- pure API / controller contract tests that run
   WITHOUT Docker. They exercise the FastAPI endpoints that start/stop the
   simulator subprocess and stream its log, plus the simulator subprocess
   itself (started with ``--once`` so it exits on its own). These prove the
   integration plumbing (subprocess spawn, rolling log, start/stop state)
   works in any environment.

2. ``test_sensor_full_pipeline`` -- the full data-flow verification. It
   requires the Docker Compose stack (zenoh + iotdb + bridge) to be running
   (``make up``). It starts the simulator through the API on a *unique* key,
   then polls Zenoh (direct subscription) and IoTDB (bridge persist) to
   confirm the value travelled all the way through, and finally stops the
   simulator and asserts both diagrams' data sources reflect it. When the
   stack is unavailable the test is skipped automatically (never faked-pass).

Run the no-Docker tests with::

    pytest tests/test_sensor_flow.py -k api -v

Run the full pipeline (needs ``make up``) with::

    pytest tests/test_sensor_flow.py -k full_pipeline -v
"""

import os
import sys
import time

import pytest

# ---------------------------------------------------------------------------
# Import the dashboard app (also pulls in app.simulator_controller). If the UI
# dependencies (panel / bokeh-fastapi) are missing we skip the whole module.
# ---------------------------------------------------------------------------
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from fastapi.testclient import TestClient
    from app import main as dashboard_app
    from app import config, simulator_controller

    APP = dashboard_app.app
    _APP_AVAILABLE = True
    _SKIP_REASON = ""
except ImportError as exc:  # pragma: no cover - depends on env
    _APP_AVAILABLE = False
    _SKIP_REASON = f"Dashboard / simulator dependencies unavailable: {exc}"


pytestmark = pytest.mark.skipif(not _APP_AVAILABLE, reason=_SKIP_REASON)


# Poll tuning -----------------------------------------------------------------
PIPELINE_WAIT_SECONDS = 15.0


@pytest.fixture
def client():
    """Synchronous in-process test client for the FastAPI app.

    Neutralises Panel's periodic callbacks: the dashboard registers Bokeh
    periodic callbacks on the event loop, but Starlette's TestClient closes
    the loop after each request, which would raise "Event loop is closed".
    The callbacks are exercised in the live container, not here.
    """
    import panel as pn

    pn.state.add_periodic_callback = lambda *a, **k: None  # type: ignore[attr-defined]
    with TestClient(APP) as c:
        yield c
    # Make sure we never leak a simulator subprocess across tests.
    simulator_controller.stop_simulator()


# ---------------------------------------------------------------------------
# Layer 1: API / controller contract tests (no Docker required)
# ---------------------------------------------------------------------------


def test_simulator_api_start_stop_and_log(client):
    """Start the simulator, confirm the API + log plumbing, then stop it.

    On a host without a reachable Zenoh broker the simulator subprocess will
    log a connection failure and exit (its intended behaviour), so we do NOT
    assert it stays in the ``running`` state here -- that is covered by the
    Docker-gated ``test_sensor_full_pipeline``. Instead we assert the API
    contract: the start endpoint launches a subprocess, the rolling log
    captures its stdout, and the stop endpoint is safe/idempotent.
    """
    # Ensure clean slate.
    simulator_controller.stop_simulator()

    resp = client.post("/api/simulator/start")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("started", "already_running")

    # Give the subprocess a moment to emit log lines.
    time.sleep(2.0)

    log = client.get("/api/simulator/log").json()
    assert "lines" in log
    # The rolling log must have captured real subprocess output (startup banner
    # and/or a Zenoh connect attempt). This proves the stdout capture works.
    assert len(log["lines"]) > 0, "simulator produced no log output"
    joined = "\n".join(log["lines"])
    assert "Simulator" in joined or "Zenoh" in joined or "zenoh" in joined

    resp = client.post("/api/simulator/stop")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("stopped", "not_running")

    status = client.get("/api/simulator/status").json()
    assert status["status"] == "stopped"


def test_simulator_api_idempotent_start(client):
    """Calling start twice should not spawn a second process."""
    simulator_controller.stop_simulator()
    first = client.post("/api/simulator/start").json()
    second = client.post("/api/simulator/start").json()
    assert first["status"] == "started"
    assert second["status"] == "already_running"
    simulator_controller.stop_simulator()


def test_simulator_api_status_in_status_endpoint(client):
    """The /api/status aggregate endpoint should include the simulator state."""
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert "simulator" in resp.json()
    assert "status" in resp.json()["simulator"]


# ---------------------------------------------------------------------------
# Layer 2: full end-to-end pipeline (requires Docker Compose stack)
# ---------------------------------------------------------------------------


def _services_available() -> bool:
    """Return True only if both Zenoh and IoTDB are reachable from the host."""
    from app.iotdb_client import IoTDBClient
    from app.zenoh_client import ZenohClient

    z_cl = ZenohClient()
    i_cl = IoTDBClient()
    z_ok = z_cl.connect(peer=config.ZENOH_HOST_ENDPOINT)
    i_ok = i_cl.connect(host="localhost", port=6667)
    if z_ok:
        z_cl.close()
    if i_ok:
        i_cl.close()
    return z_ok and i_ok


@pytest.fixture
def pipeline_services():
    """Connect clients and skip the whole pipeline test if unavailable."""
    if not _services_available():
        pytest.skip(
            "Full pipeline test requires the Docker Compose stack "
            "(zenoh + iotdb + bridge) running via 'make up'. Skipped."
        )
    from app.iotdb_client import IoTDBClient
    from app.zenoh_client import ZenohClient

    z_cl = ZenohClient()
    i_cl = IoTDBClient()
    assert z_cl.connect(peer=config.ZENOH_HOST_ENDPOINT)
    assert i_cl.connect(host="localhost", port=6667)
    i_cl.initialize_schema()
    yield z_cl, i_cl
    z_cl.close()
    i_cl.close()


def test_sensor_full_pipeline(client, pipeline_services):
    """Verify data travels simulator -> Zenoh -> bridge -> IoTDB.

    Steps:
      1. Start the simulator via the controller (deterministic fixed value on
         the production key) so we can distinguish its data from any background
         noise already in IoTDB.
      2. Subscribe to Zenoh directly and confirm the value arrives (Diagram 1
         data source).
      3. Poll IoTDB until the bridge persists the value (Diagram 2 data source).
      4. Stop the simulator via the API and assert it reports stopped.
    """
    z_cl, i_cl = pipeline_services

    # The bridge subscribes only to the *production* key expression, so we must
    # publish on that key. We distinguish our data with a unique value instead.
    # The simulator rounds every value to 2 decimals (generate_reading), so we
    # pre-round here and compare with a small tolerance.
    unique_value = round(round(21.0 + (time.time() % 5.0), 3), 2)
    prod_key = config.ZENOH_KEY_EXPRESSION

    # NOTE: The HTTP start endpoint uses configuration defaults; to inject a
    # unique value we launch through the controller directly, then verify
    # the *API* status/stop path separately (the HTTP start contract is covered
    # by test_simulator_api_start_stop_and_log in Layer 1).
    start_result = simulator_controller.start_simulator(
        value=unique_value,
        interval=1.0,
        key=prod_key,
        endpoint=config.ZENOH_HOST_ENDPOINT,
    )
    assert start_result["status"] in ("started", "already_running")
    try:
        # --- Step 2: Zenoh reception (Diagram 1 source) ---------------------
        collected = z_cl.subscribe(prod_key, timeout=8.0)
        zenoh_values = []
        for msg in collected:
            try:
                import json as _json

                data = _json.loads(msg["value"])
                zenoh_values.append(float(data.get("value", 0.0)))
            except (ValueError, TypeError):
                continue
        assert any(abs(v - unique_value) < 0.001 for v in zenoh_values), (
            f"Value {unique_value} was not observed on Zenoh key {prod_key}. "
            f"Collected: {zenoh_values}"
        )

        # --- Step 3: IoTDB persistence (Diagram 2 source) -------------------
        found = False
        deadline = time.monotonic() + PIPELINE_WAIT_SECONDS
        while time.monotonic() < deadline:
            records = i_cl.query_temperature(limit=50)
            for rec in records:
                if abs(float(rec.get("temperature", 0.0)) - unique_value) < 0.001:
                    found = True
                    break
            if found:
                break
            time.sleep(0.5)
        assert found is True, (
            f"Value {unique_value} was not bridged to IoTDB within "
            f"{PIPELINE_WAIT_SECONDS}s. Check 'docker compose logs -f zenoh-to-iotdb'."
        )
    finally:
        # --- Step 4: stop via the API and assert state ----------------------
        stop_resp = client.post("/api/simulator/stop")
        assert stop_resp.status_code == 200
        assert stop_resp.json()["status"] == "stopped"
        status = client.get("/api/simulator/status").json()
        assert status["status"] == "stopped"
        # Belt-and-suspenders: ensure the process is really gone.
        simulator_controller.stop_simulator()
