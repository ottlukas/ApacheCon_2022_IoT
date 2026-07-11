# -*- coding: utf-8 -*-
"""Process-wide controller for the sensor simulator subprocess.

The dashboard container is the natural home for the simulator when the stack
runs in Docker: the dashboard and the simulator share the same Docker network,
so the simulator can publish straight to the in-cluster Zenoh broker
(``tcp/zenoh:7447``) instead of needing a process on the host.

This module owns a single subprocess running ``scripts/sensor_simulator.py``
and exposes a small, thread-safe API used by both the FastAPI routes and the
Panel dashboard:

  * :func:`start_simulator` / :func:`stop_simulator` -- lifecycle control.
  * :func:`simulator_status` -- current state (running/stopped/error).
  * :func:`get_log` -- the rolling, tail-limited log buffer.

The simulator writes human-readable status lines to stdout (see
``scripts/sensor_simulator.py``). We capture that stream into a bounded,
thread-safe ``collections.deque`` so the dashboard can poll it without
holding the subprocess pipe open. The buffer is capped (``MAX_LOG_LINES``) so
a long-running simulator can never exhaust memory.
"""

import collections
import logging
import os
import subprocess
import sys
import threading
from typing import Dict, List, Optional

from app import config

logger = logging.getLogger("simulator_controller")

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

# Where the simulator script lives relative to the project root.  Resolved at
# import time so it works both inside the container (/app/scripts) and when
# running the repo locally.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SIMULATOR_SCRIPT = os.path.join(_PROJECT_ROOT, "scripts", "sensor_simulator.py")

# Cap the in-memory log so a long-lived simulator never OOMs the container.
MAX_LOG_LINES = int(os.getenv("SIMULATOR_LOG_MAX_LINES", "500"))

# How many log lines the API / dashboard returns per poll.
DEFAULT_LOG_TAIL = int(os.getenv("SIMULATOR_LOG_TAIL", "200"))

# Lock guarding every mutation of the shared controller state below.
_lock = threading.Lock()

# The active subprocess (None when stopped).
_process: Optional[subprocess.Popen] = None

# Rolling log buffer of decoded text lines (newest appended to the right).
_log_lines: "collections.deque[str]" = collections.deque(maxlen=MAX_LOG_LINES)

# One-word machine state used by the status endpoint / dashboard badge.
_state = "stopped"

# Human-readable detail shown alongside the state.
_state_detail = "Simulator has not been started."

# Background thread that drains the subprocess stdout pipe into ``_log_lines``.
_reader_thread: Optional[threading.Thread] = None

# Event set when the reader thread should stop (process ended / was killed).
_stop_event = threading.Event()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _append_log(line: str) -> None:
    """Append a decoded log line to the rolling buffer (lock-free; caller locks)."""
    # Drop a trailing newline so the UI can render its own line breaks.
    stripped = line.rstrip("\n").rstrip("\r")
    if stripped:
        _log_lines.append(stripped)


def _reader_loop(proc: subprocess.Popen) -> None:
    """Drain the simulator's stdout into the log buffer until EOF."""
    try:
        # proc.stdout is guaranteed non-None because we open with text=True.
        assert proc.stdout is not None
        for raw in proc.stdout:
            with _lock:
                _append_log(raw)
            if _stop_event.is_set():
                break
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Error while reading simulator stdout: %s", exc)
    finally:
        # Make sure the process resource is reaped.
        try:
            proc.wait(timeout=5)
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        with _lock:
            # Only flip to stopped if this is still the same process we started.
            if _process is proc:
                global _state, _state_detail  # noqa: PLW0603
                _state = "stopped"
                _state_detail = "Simulator process exited."
                logger.info("Simulator subprocess has exited.")


def _build_command(
    value: Optional[float] = None,
    interval: Optional[float] = None,
    key: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> List[str]:
    """Build the argv list for launching the simulator subprocess.

    Args:
        value: Fixed sensor value (deterministic mode). Defaults to random.
        interval: Publish interval override (seconds).
        key: Zenoh key expression override.
        endpoint: Zenoh endpoint override.
    """
    python = sys.executable or "python"
    cmd = [
        python,
        SIMULATOR_SCRIPT,
        # Point the simulator at the Zenoh broker this container can reach.
        "--endpoint",
        endpoint or config.ZENOH_ENDPOINT,
        "--key",
        key or config.ZENOH_KEY_EXPRESSION,
        "--interval",
        str(interval if interval is not None else config.SIMULATOR_INTERVAL_SECONDS),
        "--min",
        str(config.SIMULATOR_MIN_VALUE),
        "--max",
        str(config.SIMULATOR_MAX_VALUE),
        "--device",
        config.IOTDB_DEVICE.split(".")[-1],
        "--measurement",
        config.IOTDB_MEASUREMENT,
    ]
    if value is not None:
        cmd += ["--value", str(value)]
    return cmd


def _check_alive() -> bool:
    """Return True iff the tracked process is still running."""
    with _lock:
        if _process is None:
            return False
        return _process.poll() is None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_simulator(
    value: Optional[float] = None,
    interval: Optional[float] = None,
    key: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> Dict[str, str]:
    """Start the sensor simulator subprocess if it is not already running.

    Args:
        value: Fixed sensor value (deterministic mode). Defaults to random.
        interval: Publish interval override (seconds).
        key: Zenoh key expression override.
        endpoint: Zenoh endpoint override (e.g. ``tcp/localhost:7447``).

    Returns:
        A status dict with ``status`` (``started`` / ``already_running`` /
        ``error``) and a human-readable ``message``.
    """
    global _process, _reader_thread, _state, _state_detail  # noqa: PLW0603

    with _lock:
        # Already running?
        if _process is not None and _process.poll() is None:
            return {
                "status": "already_running",
                "message": "Sensor simulator is already running.",
            }

        if not os.path.exists(SIMULATOR_SCRIPT):
            _state = "error"
            _state_detail = f"Simulator script not found at {SIMULATOR_SCRIPT}."
            logger.error("Cannot start simulator: %s not found", SIMULATOR_SCRIPT)
            return {
                "status": "error",
                "message": f"Simulator script not found at {SIMULATOR_SCRIPT}.",
            }

        try:
            cmd = _build_command(value=value, interval=interval, key=key, endpoint=endpoint)
            logger.info("Launching sensor simulator: %s", " ".join(cmd))
            _stop_event.clear()
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # merge so errors also land in the log
                text=True,
                bufsize=1,  # line-buffered
                # Dashboard runs as a non-root user with /app as cwd; scripts/
                # is copied next to app/ so the default cwd works. The simulator
                # inserts the project root onto sys.path itself.
            )
            _process = proc
            _state = "running"
            _state_detail = (
                f"Publishing to Zenoh {config.ZENOH_ENDPOINT} on "
                f"{config.ZENOH_KEY_EXPRESSION}."
            )
            _reader_thread = threading.Thread(
                target=_reader_loop, args=(proc,), daemon=True
            )
            _reader_thread.start()
            logger.info("Sensor simulator started (pid=%s).", proc.pid)
            return {
                "status": "started",
                "message": "Sensor simulator started and publishing to Zenoh.",
            }
        except Exception as exc:  # pylint: disable=broad-exception-caught
            _state = "error"
            _state_detail = f"Failed to start simulator: {exc}"
            logger.error("Failed to start simulator: %s", exc)
            return {
                "status": "error",
                "message": f"Failed to start simulator: {exc}",
            }


def stop_simulator() -> Dict[str, str]:
    """Stop the sensor simulator subprocess if it is running.

    Returns:
        A status dict with ``status`` (``stopped`` / ``not_running`` /
        ``error``) and a human-readable ``message``.
    """
    global _process, _reader_thread, _state, _state_detail  # noqa: PLW0603

    with _lock:
        proc = _process
        if proc is None or proc.poll() is not None:
            return {
                "status": "not_running",
                "message": "No sensor simulator is currently running.",
            }

        logger.info("Stopping sensor simulator (pid=%s) …", proc.pid)
        _stop_event.set()
        try:
            proc.terminate()  # SIGTERM -> simulator's signal handler sets running=False
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("Simulator did not exit after SIGTERM; sending SIGKILL.")
                proc.kill()
                proc.wait(timeout=5)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            _state = "error"
            _state_detail = f"Error while stopping simulator: {exc}"
            logger.error("Error while stopping simulator: %s", exc)
            return {
                "status": "error",
                "message": f"Error while stopping simulator: {exc}",
            }
        finally:
            _process = None
            _reader_thread = None
            _state = "stopped"
            _state_detail = "Sensor simulator stopped."
            logger.info("Sensor simulator stopped.")

        return {
            "status": "stopped",
            "message": "Sensor simulator stopped.",
        }


def simulator_status() -> Dict[str, str]:
    """Return the current simulator state and a detail string."""
    global _state, _state_detail  # noqa: PLW0603
    with _lock:
        alive = _process is not None and _process.poll() is None
        # Reconcile state if the process died on its own.
        if _state == "running" and not alive and _process is not None:
            _state = "stopped"
            _state_detail = "Simulator process exited unexpectedly."
        return {
            "status": _state,
            "detail": _state_detail,
            "running": str(alive),
        }


def get_log(tail: int = DEFAULT_LOG_TAIL) -> Dict[str, object]:
    """Return the most recent simulator log lines.

    Args:
        tail: Maximum number of lines to return (capped at ``MAX_LOG_LINES``).

    Returns:
        A dict with ``lines`` (list of strings), ``status`` and ``detail`` so a
        single poll gives the UI everything it needs to render the panel.
    """
    with _lock:
        lines = list(_log_lines)[-max(1, min(int(tail), MAX_LOG_LINES)) :]
        alive = _process is not None and _process.poll() is None
        return {
            "lines": lines,
            "status": _state,
            "detail": _state_detail,
            "running": alive,
        }
