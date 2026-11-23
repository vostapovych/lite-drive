import os

# Must be set before any server/Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LITEDRIVE_FAKE_SUPABASE"] = "1"

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.config import Settings
from server.supabase_client import FakeSupabase


@pytest.fixture
def sb() -> FakeSupabase:
    return FakeSupabase()


@pytest.fixture
def client(sb) -> TestClient:
    return TestClient(create_app(Settings(litedrive_fake_supabase=True), sb))


def login(client: TestClient, email: str, password: str) -> dict:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


@pytest.fixture
def live_server(sb):
    """Real uvicorn on a free port in a thread, backed by the fake. Yields the base URL."""
    import socket
    import threading
    import time

    import uvicorn

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    app = create_app(Settings(litedrive_fake_supabase=True), sb)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.02)
    assert server.started, "uvicorn did not start"
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    t.join(timeout=5)


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def alice(client):
    return login(client, "alice@example.com", "alice123")


@pytest.fixture
def bob(client):
    return login(client, "bob@example.com", "bob123")
