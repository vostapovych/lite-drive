"""SessionStore(save, bearer, clear). The token lives in memory only; just the server URL/email are remembered."""
from __future__ import annotations

from PySide6.QtCore import QSettings

DEFAULT_URL = "http://127.0.0.1:8000"


class SessionStore:
    def __init__(self, settings: QSettings | None = None):
        self._settings = settings
        self._token: str | None = None
        self.email: str = ""

    def save(self, token: str, email: str = "", base_url: str | None = None) -> None:
        self._token, self.email = token, email
        if self._settings is not None:
            self._settings.setValue("session/email", email)
            if base_url:
                self._settings.setValue("session/baseUrl", base_url)

    def bearer(self) -> str | None:
        return self._token

    def clear(self) -> None:
        self._token = None

    def remembered(self) -> tuple[str, str]:
        if self._settings is None:
            return DEFAULT_URL, ""
        return (str(self._settings.value("session/baseUrl", DEFAULT_URL)),
                str(self._settings.value("session/email", "")))
