"""FileListController(refresh, delete) + preview fetching. Owns no widgets; talks to ApiClient on worker threads."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox, QWidget

from client_desktop.api_client import ApiClient
from client_desktop.models import FileItem, FileTableModel
from client_desktop.workers import run_async


def ask_confirm(parent: QWidget | None, text: str) -> bool:
    box = QMessageBox(QMessageBox.Icon.Warning, "Delete file", text,
                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, parent)
    box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    box.setObjectName("deleteConfirm")
    return box.exec() == QMessageBox.StandardButton.Yes


class FileListController(QObject):
    refreshed = Signal(int)
    deleted = Signal(str)
    failed = Signal(str)

    def __init__(self, api: ApiClient, model: FileTableModel, parent: QObject | None = None):
        super().__init__(parent)
        self.api = api
        self.model = model
        # injectable so tests/screenshots can drive the confirmation dialog
        self.confirm: Callable[[QWidget | None, str], bool] = ask_confirm
        self.dialog_parent: QWidget | None = None

    def _err(self, exc) -> None:
        self.failed.emit(getattr(exc, "message", str(exc)))

    def refresh(self) -> None:
        def done(rows):
            self.model.set_items([FileItem.from_api(r) for r in rows])
            self.refreshed.emit(len(rows))
        run_async(self.api.listFiles, done, self._err)

    def delete(self, items: list[FileItem]) -> None:
        if not items:
            return
        if len(items) == 1:
            text = f"Delete “{items[0].name}” from your drive?\nThis cannot be undone."
        else:
            text = f"Delete {len(items)} files from your drive?\nThis cannot be undone."
        if not self.confirm(self.dialog_parent, text):
            return

        def work():
            for it in items:
                self.api.delete(it.id)

        def done(_):
            self.deleted.emit(", ".join(i.name for i in items))
            self.refresh()
        run_async(work, done, self._err)

    def load_preview(self, item: FileItem, on_data: Callable[[str, bytes], None], on_error: Callable[[str, str], None]) -> None:
        name = item.name
        run_async(lambda: self.api.fetch(self.api.downloadUrl(item.id)["url"]),
                  lambda data: on_data(name, data),
                  lambda exc: on_error(name, getattr(exc, "message", str(exc))))
