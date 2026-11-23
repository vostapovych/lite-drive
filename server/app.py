"""FastAPI app factory. `uvicorn server.app:app --host 0.0.0.0 --port $PORT`."""
from fastapi import FastAPI

from server.config import Settings, get_settings
from server.routers import auth, files, transfers
from server.services import AuthService, FileService, TransferService
from server.supabase_client import FakeSupabase, SupabaseClient, build_supabase


def create_app(settings: Settings | None = None, sb: SupabaseClient | None = None) -> FastAPI:
    settings = settings or get_settings()
    sb = sb or build_supabase(settings)
    app = FastAPI(title="Lite Drive")
    app.state.sb = sb
    app.state.auth_service = AuthService(sb)
    app.state.file_service = FileService(sb)
    app.state.transfer_service = TransferService(sb, app.state.file_service)

    app.include_router(auth.router)
    app.include_router(files.router)
    app.include_router(transfers.router)

    if isinstance(sb, FakeSupabase):
        from server import fake_storage

        app.include_router(fake_storage.router)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    try:  # web client (Day 4) mounts its page routes on this same app
        from client_web import mount

        mount(app)
    except ImportError:
        pass
    return app


app = create_app()
