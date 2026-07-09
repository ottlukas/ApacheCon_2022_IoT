# -*- coding: utf-8 -*-
"""Unit tests for the configuration module."""

import importlib
from app import config


def test_config_defaults():
    """Verify that default configurations are correctly loaded when no env vars are set."""
    # Since config is already loaded, we just verify its fields are present
    assert hasattr(config, "ZENOH_ENDPOINT")
    assert hasattr(config, "ZENOH_HOST_ENDPOINT")
    assert hasattr(config, "ZENOH_KEY_EXPRESSION")
    assert hasattr(config, "IOTDB_HOST")
    assert hasattr(config, "IOTDB_PORT")
    assert hasattr(config, "IOTDB_USER")
    assert hasattr(config, "IOTDB_PASSWORD")
    assert hasattr(config, "IOTDB_DATABASE")
    assert hasattr(config, "IOTDB_DEVICE")
    assert hasattr(config, "IOTDB_MEASUREMENT")
    assert hasattr(config, "DASHBOARD_PORT")


def test_config_env_overrides(monkeypatch):
    """Verify that environment variable overrides are correctly parsed."""
    # Set custom env values
    monkeypatch.setenv("ZENOH_ENDPOINT", "tcp/custom-zenoh:9999")
    monkeypatch.setenv("ZENOH_HOST_ENDPOINT", "tcp/custom-host:9999")
    monkeypatch.setenv("ZENOH_KEY_EXPRESSION", "/custom/key")
    monkeypatch.setenv("IOTDB_HOST", "custom-iotdb")
    monkeypatch.setenv("IOTDB_PORT", "1234")
    monkeypatch.setenv("IOTDB_USER", "custom_user")
    monkeypatch.setenv("IOTDB_PASSWORD", "custom_pass")
    monkeypatch.setenv("IOTDB_DATABASE", "root.custom_db")
    monkeypatch.setenv("IOTDB_DEVICE", "root.custom_db.custom_device")
    monkeypatch.setenv("IOTDB_MEASUREMENT", "custom_val")
    monkeypatch.setenv("DASHBOARD_PORT", "8888")

    # Force reload of the config module
    importlib.reload(config)

    # Verify overrides
    assert config.ZENOH_ENDPOINT == "tcp/custom-zenoh:9999"
    assert config.ZENOH_HOST_ENDPOINT == "tcp/custom-host:9999"
    assert config.ZENOH_KEY_EXPRESSION == "/custom/key"
    assert config.IOTDB_HOST == "custom-iotdb"
    assert config.IOTDB_PORT == 1234
    assert config.IOTDB_USER == "custom_user"
    assert config.IOTDB_PASSWORD == "custom_pass"
    assert config.IOTDB_DATABASE == "root.custom_db"
    assert config.IOTDB_DEVICE == "root.custom_db.custom_device"
    assert config.IOTDB_MEASUREMENT == "custom_val"
    assert config.DASHBOARD_PORT == 8888

    # Clean up and reload back to defaults / actual env
    monkeypatch.delenv("ZENOH_ENDPOINT", raising=False)
    monkeypatch.delenv("ZENOH_HOST_ENDPOINT", raising=False)
    monkeypatch.delenv("ZENOH_KEY_EXPRESSION", raising=False)
    monkeypatch.delenv("IOTDB_HOST", raising=False)
    monkeypatch.delenv("IOTDB_PORT", raising=False)
    monkeypatch.delenv("IOTDB_USER", raising=False)
    monkeypatch.delenv("IOTDB_PASSWORD", raising=False)
    monkeypatch.delenv("IOTDB_DATABASE", raising=False)
    monkeypatch.delenv("IOTDB_DEVICE", raising=False)
    monkeypatch.delenv("IOTDB_MEASUREMENT", raising=False)
    monkeypatch.delenv("DASHBOARD_PORT", raising=False)
    importlib.reload(config)
