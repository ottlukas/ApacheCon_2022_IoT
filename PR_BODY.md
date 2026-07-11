## Issue Fixed
The Apache ECharts dashboard did not render in the containerized Panel app
(`uvicorn app.main:app`, mounted at /panel). The whole dashboard returned a
blank/500 page because building the view raised an exception before the
ECharts panes were created.

## Root Cause
`app/dashboard.py` constructed the sidebar logo from a hard-coded absolute
path and passed it to `pn.pane.JPG(..., embed=True)`:

    pn.pane.JPG("/app/app/asf-estd-1999-logo.jpg", embed=True)

With `embed=True`, Panel fetches the image via `requests.get`. A scheme-less
path raises `requests.exceptions.MissingSchema`, which propagated through
`template.server_doc` and aborted the entire dashboard render — so the
ECharts panes never appeared. (The standalone `panel_script.py` already
handled this correctly; the container-served `app/dashboard.py` did not.)

## Changes Made
- **Code (`app/dashboard.py`)**: resolve the logo path relative to the package
  (`os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", ...)`) and
  guard the embed with `os.path.exists`, so a missing/incorrect path can never
  crash the render. Added `import os` and explanatory comments.
- **Dependencies**: no required change — current Panel (resolved by
  `panel>=1.3.0`) bundles ECharts locally under
  `static/extensions/panel/bundled/echarts/` (no runtime CDN/internet).
  CI pins `panel>=1.4.0` to avoid older CDN-loading releases.
- **Tests**:
  - `tests/test_dashboard_echarts.py` — unit tests for `create_echarts_option`
    and mocked `pn.pane.ECharts` construction (data/axes/series wiring).
  - `tests/test_dashboard_integration.py` — boots the exact FastAPI+Panel app
    in-process and asserts `GET /panel` returns 200 with ECharts bundled
    locally (no CDN). Also keeps `/health` working (no regression).
  - `tests/test_dashboard_e2e.py` — Playwright headless-browser test asserting
    the ECharts canvases mount and receive data; skips cleanly without a
    server/browser.
  - `.github/workflows/dashboard-tests.yml` — runs the rendering tests on PRs.
- **Documentation (`README.md`)**: how to run the rendering tests, expanded
  test coverage list, and troubleshooting for the blank-dashboard and
  offline-ECharts-load failure modes.

## Testing Approach & Results
- Unit + integration: 9/9 passed (no Docker/browser required).
- Full suite: 11 passed, 12 skipped (skips are conditional on live
  Zenoh/IoTDB/Playwright).
- Verified the exact failure mode: `/panel` raised `MissingSchema` before the
  fix and returns HTTP 200 with the ECharts library embedded locally after.

## Open Questions / Edge Cases
- In-browser canvas drawing is best confirmed by the E2E test once a running
  server (container or host) is available.
- Pinning `panel<1.4` would reintroduce CDN loading; keep `panel>=1.4.0`.
