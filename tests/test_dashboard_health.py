# -*- coding: utf-8 -*-
"""Integration tests for the dashboard endpoints and health status."""

import pytest
import httpx
from app import config


@pytest.fixture(scope="module")
def dashboard_url():
    """Verify if dashboard is running, otherwise skip tests."""
    url = f"http://localhost:{config.DASHBOARD_PORT}"
    try:
        # Check if dashboard is up
        response = httpx.get(f"{url}/health", timeout=2.0)
        if response.status_code != 200:
            pytest.skip(
                f"Dashboard returned status {response.status_code}. " "Integration tests skipped."
            )
    except (httpx.HTTPError, ConnectionError):
        pytest.skip(f"Dashboard service is not running at {url}. Integration tests skipped.")
    return url


def test_dashboard_health_endpoint(dashboard_url):
    """Verify that GET /health returns 200 OK and correct JSON structure."""
    response = httpx.get(f"{dashboard_url}/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert "zenoh_connected" in data
    assert "iotdb_connected" in data


def test_dashboard_status_endpoint(dashboard_url):
    """Verify that GET /api/status returns 200 OK and detailed service stats."""
    response = httpx.get(f"{dashboard_url}/api/status")
    assert response.status_code == 200

    data = response.json()
    assert "timestamp" in data
    assert "services" in data

    services = data["services"]
    assert "zenoh" in services
    assert "iotdb" in services

    assert "connected" in services["zenoh"]
    assert "connected" in services["iotdb"]


def test_dashboard_panel_page(dashboard_url):
    """Verify that GET /panel returns HTML content (Panel app index)."""
    # Follow redirects as the root might redirect
    response = httpx.get(f"{dashboard_url}/panel", follow_redirects=True)
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert len(response.text) > 0
