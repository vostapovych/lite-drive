"""ApiClient: the desktop's only door to the server (and to signed storage URLs). Synchronous httpx;
call it from worker threads. Signed URLs may be relative (FakeSupabase dev mount) -> joined with base_url."""
from __future__ import annotations

from datetime import datetime
from urllib.parse import urljoin

import httpx

from client_desktop.session_store import SessionStore


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class ApiClient:
    def __init__(self, session: SessionStore, base_url: str = "http://127.0.0.1:8000", http: httpx.Client | None = None):
        self.session = session
        self.base_url = base_url.rstrip("/")
        # Generous timeout: a sleeping Render free service takes up to ~60 s to wake.
        self.http = http or httpx.Client(timeout=httpx.Timeout(90.0, connect=90.0))

    def set_base_url(self, url: str) -> None:
        self.base_url = url.rstrip("/")

    # --- helpers ---
    def _abs(self, url: str) -> str:
        return urljoin(self.base_url + "/", url)

    def _auth(self) -> dict:
        tok = self.session.bearer()
        return {"Authorization": f"Bearer {tok}"} if tok else {}

    @staticmethod
    def _check(r: httpx.Response) -> httpx.Response:
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except Exception:
                detail = r.text
            raise ApiError(r.status_code, str(detail))
        return r

    def _call(self, method: str, path: str, **kw) -> httpx.Response:
        try:
            return self._check(self.http.request(method, self._abs(path), headers=self._auth(), **kw))
        except httpx.HTTPError as e:
            raise ApiError(0, f"Cannot reach server: {e}") from e

    # --- API ---
    def login(self, email: str, password: str) -> None:
        r = self._call("POST", "/auth/login", json={"email": email, "password": password})
        self.session.save(r.json()["accessToken"], email, self.base_url)

    def logout(self) -> None:
        try:
            self._call("POST", "/auth/logout")
        except ApiError:
            pass
        self.session.clear()

    def listFiles(self) -> list[dict]:
        return self._call("GET", "/files").json()

    def requestUpload(self, name: str, size: int) -> dict:
        return self._call("POST", "/uploads", json={"name": name, "size": size}).json()

    def putObject(self, upload_url: str, data: bytes) -> None:
        """PUT bytes straight to Storage (signed URL). Never goes through the API routes."""
        try:
            self._check(self.http.put(self._abs(upload_url), content=data,
                                      headers={"Content-Type": "application/octet-stream", "x-upsert": "true"}))
        except httpx.HTTPError as e:
            raise ApiError(0, f"Upload failed: {e}") from e

    def commit(self, file_id: str, modified_at: datetime | None = None, size: int | None = None) -> dict:
        body: dict = {}
        if modified_at is not None:
            body["modifiedAt"] = modified_at.isoformat()
        if size is not None:
            body["size"] = size
        return self._call("POST", f"/files/{file_id}/commit", json=body).json()

    def downloadUrl(self, file_id: str) -> dict:
        return self._call("GET", f"/files/{file_id}/download-url").json()

    def fetch(self, url: str) -> bytes:
        """GET bytes from a signed Storage URL."""
        try:
            return self._check(self.http.get(self._abs(url))).content
        except httpx.HTTPError as e:
            raise ApiError(0, f"Download failed: {e}") from e

    def delete(self, file_id: str) -> None:
        self._call("DELETE", f"/files/{file_id}")
