"""
Shared pytest fixtures.

Provides a session-scoped, in-process instance of the FastAPI application so
that the integration tests (which issue real HTTP requests to port 6668) are
fully self-contained: no external server or supervisor process is required,
and the server under test always reflects the current source code.
"""
import os
import sys
import time
import socket
import threading

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

HOST = "127.0.0.1"
PORT = 6668


def _port_open(host: str, port: int) -> bool:
    """Return True if something is accepting TCP connections on host:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


@pytest.fixture(scope="session", autouse=True)
def api_server():
    """Run the FastAPI app in-process for the duration of the test session.

    If a healthy server is already listening on the port it is reused;
    otherwise a fresh uvicorn server is started in a daemon thread and torn
    down automatically at the end of the session.
    """
    import uvicorn
    from src.api.main import app

    # Reuse an already-running, healthy server (e.g. a dev instance).
    if _port_open(HOST, PORT):
        yield
        return

    config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    # Signal handlers can only be installed on the main thread; disable them
    # since the server runs in a worker thread here.
    server.install_signal_handlers = lambda: None

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait until the server accepts connections (max ~10s).
    for _ in range(100):
        if _port_open(HOST, PORT):
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("In-process API server failed to start on port 6668")

    yield

    server.should_exit = True
    thread.join(timeout=5)
