"""SyncController(bind, synchronise): scan local + list remote -> SyncPlanner.plan -> run actions on the TransferQueue.
Never deletes. Uploads carry the local mtime; downloads set the local mtime to the server's value."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from client_desktop.api_client import ApiClient
from client_desktop.folder_watcher import FolderWatcher
from client_desktop.sync_planner import RemoteFile, SyncKind, SyncPlanner
from client_desktop.transfers import TransferQueue, TransferTask, do_download, do_upload
from client_desktop.workers import run_async


class SyncController(QObject):
    synchronised = Signal(dict)  # {"uploaded": n, "downloaded": n, "skipped": n, "errors": [..]}
    failed = Signal(str)
    bound = Signal(str)

    def __init__(self, api: ApiClient, queue: TransferQueue, watcher: FolderWatcher | None = None,
                 parent: QObject | None = None):
        super().__init__(parent)
        self.api = api
        self.queue = queue
        self.planner = SyncPlanner()
        self.watcher = watcher or FolderWatcher(self)
        self.folder: str | None = None
        self.auto_sync = True
        self._running = False
        self._dirty = False
        self._counts: dict = {}
        self._planned_up = self._planned_down = 0
        queue.allDone.connect(self._on_queue_done)
        self.watcher.changed.connect(self._on_folder_changed)

    def bind(self, folder: str) -> None:
        self.folder = str(folder)
        self.watcher.start(self.folder)
        self.bound.emit(self.folder)

    def synchronise(self) -> None:
        if not self.folder:
            self.failed.emit("Bind a local folder first.")
            return
        if self._running:
            self._dirty = True  # re-run once the current pass ends
            return
        self._running, self._dirty = True, False
        folder = self.folder

        def gather():
            return self.watcher.scan(folder), self.api.listFiles()

        run_async(gather, self._planned, self._fail)

    def _fail(self, exc) -> None:
        self._running = False
        self.failed.emit(getattr(exc, "message", str(exc)))

    def _planned(self, result) -> None:
        local, rows = result
        remote = {r["name"]: RemoteFile(r["id"], r["name"], datetime.fromisoformat(r["modifiedAt"])) for r in rows}
        actions = self.planner.plan(self.folder, local, remote)
        self._counts = {"uploaded": 0, "downloaded": 0,
                        "skipped": sum(a.kind is SyncKind.SKIP for a in actions), "errors": []}
        folder = Path(self.folder)
        todo = 0
        for a in actions:
            if a.kind is SyncKind.UPLOAD:
                path, mtime = str(folder / a.name), local[a.name].modified_at
                self.queue.submit(TransferTask(f"↑ {a.name}", lambda p=path, m=mtime: do_upload(self.api, p, m)))
                todo += 1
            elif a.kind is SyncKind.DOWNLOAD:
                self.queue.submit(TransferTask(f"↓ {a.name}",
                                               lambda i=a.remote_id, n=a.name: do_download(self.api, i, folder, n)))
                todo += 1
        self._planned_up = sum(a.kind is SyncKind.UPLOAD for a in actions)
        self._planned_down = sum(a.kind is SyncKind.DOWNLOAD for a in actions)
        if todo == 0:
            self._finish([])

    def _on_queue_done(self, ok: int, errors: list) -> None:
        if not self._running:
            return
        self._finish(errors)

    def _finish(self, errors: list) -> None:
        # planned counts minus failures (task labels start with ↑ / ↓)
        self._counts["uploaded"] = self._planned_up - sum(e.startswith("↑") for e in errors)
        self._counts["downloaded"] = self._planned_down - sum(e.startswith("↓") for e in errors)
        self._counts["errors"] = list(errors)
        self._running = False
        self.synchronised.emit(self._counts)
        if self._dirty and self.auto_sync:
            self.synchronise()

    def _on_folder_changed(self) -> None:
        if self.auto_sync and self.folder:
            self.synchronise()
