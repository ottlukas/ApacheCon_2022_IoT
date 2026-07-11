# -*- coding: utf-8 -*-
"""Integration tests for the Panel/Apache ECharts dashboard served by FastAPI.

The container runs ``uvicorn app.main:app`` and mounts the Panel dashboard at
``/panel`` via ``pn.io.fastapi.add_application``. These tests exercise that
exact ASGI app *in-process* (no separate server process) so they run in CI
without Docker. They verify:

  * The app imports and the dashboard mounts without raising.
  * ``GET /panel`` returns HTTP 200 and embeds the ECharts library + the
    Bokeh server bootstrap (i.e. the page actually renders a live dashboard).
  * The ECharts assets are served locally (no hard CDN dependency that would
    break in an offline container).

A real browser test lives in ``tests/test_dashboard_e2e.py`` (Playwright) and
is skipped automatically when the browser is not installed.
"""

import os
import sys

import pytest

# The app.main module imports panel + panel.io.fastapi, which in turn triggers
# the bokeh-fastapi availability check. If those UI deps are missing we skip.
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import panel as pn  # noqa: E402  (UI dep; needed to neutralise periodic callbacks)
    from fastapi.testclient import TestClient
    from app import main as dashboard_app  # noqa: E402

    APP = dashboard_app.app
    _APP_AVAILABLE = True
    _SKIP_REASON = ""
except ImportError as exc:  # pragma: no cover - depends on env
    _APP_AVAILABLE = False
    _SKIP_REASON = f"Dashboard dependencies unavailable: {exc}"


pytestmark = pytest.mark.skipif(not _APP_AVAILABLE, reason=_SKIP_REASON)


@pytest.fixture
def client(monkeypatch):
    """Synchronous test client for the FastAPI+Panel ASGI app.

    ``create_dashboard`` registers Bokeh/Tornado periodic callbacks on the
    server's event loop. Starlette's ``TestClient`` drives the app through a
    short-lived portal whose event loop is closed after each request, which
    makes Bokeh's ``add_periodic_callback`` raise ``Event loop is closed``.
    Those callbacks are exercised elsewhere (live container) and are not what
    those rendering tests assert, so we neutralise them here.
    """
    monkeypatch.setattr(pn.state, "add_periodic_callback", lambda *a, **k: None)
    with TestClient(APP) as c:
        yield c


def test_health_endpoint_still_works(client):
    """The dashboard fix must not regress the existing health endpoint."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "zenoh_connected" in body
    assert "iotdb_connected" in body


def test_panel_route_renders_without_error(client):
    """GET /panel must return 200 after the logo-path fix.

    Before the fix, ``create_dashboard`` raised
    ``requests.exceptions.MissingSchema`` while resolving the hard-coded
    logo path, which aborted ``template.server_doc`` and produced a 500 /
    blank page -- the ECharts panes never rendered.
    """
    resp = client.get("/panel", follow_redirects=False)
    assert resp.status_code == 200, resp.text[:500]
    assert "text/html" in resp.headers.get("content-type", "")


def test_panel_page_loads_echarts_library(client):
    """The served HTML must reference the ECharts library locally."""
    resp = client.get("/panel", follow_redirects=False)
    html = resp.text
    # ECharts JS must be present and served from the bundled (local) assets,
    # NOT from an external CDN (which would fail in an offline container).
    assert "echarts" in html.lower()
    assert "echarts.min.js" in html
    assert "static/extensions/panel/bundled/echarts" in html


def test_panel_page_bootstraps_a_live_bokeh_session(client):
    """The page must include the Bokeh bootstrap so the dashboard is live."""
    resp = client.get("/panel", follow_redirects=False)
    html = resp.text
    # The bokeh application script is what turns the static HTML into a live
    # Panel session that instantiates the ECharts panes in the browser.
    assert "bokeh" in html.lower()
