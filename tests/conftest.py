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
def alice(client):
    return login(client, "alice@example.com", "alice123")


@pytest.fixture
def bob(client):
    return login(client, "bob@example.com", "bob123")
