"""Web client: Jinja2 page routes + static assets on the SAME FastAPI app as the REST API.

No API endpoints are added here (by design): the pages only serve HTML shells. The browser then talks to the
very same REST API as the desktop client (/auth/login, /files, /uploads, ...) with a Bearer token."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))


def mount(app: FastAPI) -> None:
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

    @app.get("/", include_in_schema=False)
    def drive_page(request: Request):
        return templates.TemplateResponse(request, "drive.html", {})

    @app.get("/login", include_in_schema=False)
    def login_page(request: Request):
        return templates.TemplateResponse(request, "login.html", {})
