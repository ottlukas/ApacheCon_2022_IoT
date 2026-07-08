#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for src.client_utils

This test accesses internal client attributes and defines a tiny helper
class; disable some pylint checks that are inappropriate for tests.
"""

# pylint: disable=trailing-whitespace,too-few-public-methods,protected-access
from unittest.mock import MagicMock

from src.client_utils import is_connected, close_connection


class DummyClient:
    def __init__(self):
        self._session = None
        self._connected = False
        self._subscribers = {}
        self._workspace = None


def test_is_connected_false_by_default():
    c = DummyClient()
    assert is_connected(c) is False


def test_is_connected_true_when_session_present():
    c = DummyClient()
    c._session = MagicMock()
    c._connected = True
    assert is_connected(c) is True


def test_close_connection_closes_session_and_subscribers():
    c = DummyClient()
    mock_session = MagicMock()
    mock_sub = MagicMock()
    c._session = mock_session
    c._connected = True
    c._subscribers = {"s": mock_sub}
    c._workspace = MagicMock()

    close_connection(c)

    mock_sub.close.assert_called_once()
    mock_session.close.assert_called_once()
    assert c._session is None
    assert c._connected is False
    assert c._workspace is None
    assert not c._subscribers
