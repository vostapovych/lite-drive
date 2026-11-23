"""Shared by the screenshot scripts: the real FastAPI app on a free port, backed by the seeded in-memory FakeSupabase."""
import os
import socket
import sys
import threading
import time
from pathlib import Path

os.environ["LITEDRIVE_FAKE_SUPABASE"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402

from server.app import create_app  # noqa: E402
from server.config import Settings  # noqa: E402
from server.supabase_client import FakeSupabase  # noqa: E402


def start_demo_server():
    """Returns (base_url, FakeSupabase, stop())."""
    sb = FakeSupabase()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(Settings(litedrive_fake_supabase=True), sb),
                                           host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    end = time.time() + 10
    while not server.started and time.time() < end:
        time.sleep(0.02)

    def stop():
        server.should_exit = True
        t.join(timeout=5)

    return f"http://127.0.0.1:{port}", sb, stop
