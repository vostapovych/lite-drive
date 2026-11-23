"""TransferTask(run) / TransferQueue(submit) / TransferController(upload, download).

Bytes always move client <-> Storage through the signed URLs the API hands out; the API only reserves/commits."""
from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from client_desktop.api_client import ApiClient
from client_desktop.models import FileItem
from client_desktop.workers import _Signals


def safe_local_name(name: str) -> str:
    """File names come from the server; never let one escape the target folder."""
    return Path(name.replace("\\", "/")).name


def mtime_to_dt(path: str | Path) -> datetime:
    return datetime.fromtimestamp(os.stat(path).st_mtime, tz=timezone.utc)


# ---- the actual transfer operations (used by tasks; blocking, run on worker threads) ----
def do_upload(api: ApiClient, path: str, modified_at: datetime | None = None) -> None:
    p = Path(path)
    data = p.read_bytes()
    reserved = api.requestUpload(p.name, len(data))  # 1. reserve
    api.putObject(reserved["uploadUrl"], data)  # 2. PUT to Storage via signed URL
    api.commit(reserved["fileId"], modified_at, len(data))  # 3. commit


def do_download(api: ApiClient, file_id: str, dest_dir: str | Path, fallback_name: str = "") -> Path:
    info = api.downloadUrl(file_id)
    data = api.fetch(info["url"])
    target = Path(dest_dir) / safe_local_name(info.get("name") or fallback_name)
    target.write_bytes(data)
    modified = datetime.fromisoformat(info["modifiedAt"])
    ts = modified.timestamp()
    os.utime(target, (ts, ts))  # local mtime := server modifiedAt
    return target


class TransferTask(QRunnable):
    def __init__(self, label: str, fn: Callable[[], object]):
        super().__init__()
        self.label = label
        self.fn = fn
        self.signals = _Signals()
        self.setAutoDelete(False)

    def run(self) -> None:
        try:
            self.fn()
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit((self.label, getattr(exc, "message", str(exc))))
        else:
            self.signals.done.emit(self.label)


class TransferQueue(QObject):
    """Runs tasks on a small pool; emits allDone(ok_count, errors) when the queue drains."""
    allDone = Signal(int, list)
    taskDone = Signal(str)
    taskFailed = Signal(str, str)

    def __init__(self, parent: QObject | None = None, max_threads: int = 3):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(max_threads)
        self._pending = 0
        self._ok = 0
        self._errors: list[str] = []
        self._tasks: set[TransferTask] = set()

    @property
    def pending(self) -> int:
        return self._pending

    def submit(self, task: TransferTask) -> None:
        self._pending += 1
        self._tasks.add(task)
        task.signals.done.connect(lambda label, t=task: self._finish(t, label, None))
        task.signals.failed.connect(lambda err, t=task: self._finish(t, err[0], err[1]))
        self.pool.start(task)

    def _finish(self, task: TransferTask, label: str, error: str | None) -> None:
        self._tasks.discard(task)
        self._pending -= 1
        if error is None:
            self._ok += 1
            self.taskDone.emit(label)
        else:
            self._errors.append(f"{label}: {error}")
            self.taskFailed.emit(label, error)
        if self._pending == 0:
            ok, errs = self._ok, self._errors
            self._ok, self._errors = 0, []
            self.allDone.emit(ok, errs)


class TransferController(QObject):
    batchFinished = Signal(str, int, list)  # "upload"/"download", ok_count, errors

    def __init__(self, api: ApiClient, queue: TransferQueue, parent: QObject | None = None):
        super().__init__(parent)
        self.api = api
        self.queue = queue
        self._kinds: list[str] = []
        queue.allDone.connect(self._on_done)
        self._drag_dir: str | None = None

    def _on_done(self, ok: int, errors: list) -> None:
        if self._kinds:
            self.batchFinished.emit(self._kinds.pop(0), ok, errors)

    def upload(self, paths: list[str]) -> int:
        files = [p for p in paths if Path(p).is_file()]  # flat drive: ignore folders
        if not files:
            return 0
        self._kinds.append("upload")
        for p in files:
            self.queue.submit(TransferTask(Path(p).name, lambda p=p: do_upload(self.api, p)))
        return len(files)

    def download(self, items: list[FileItem], dest_dir: str) -> int:
        if not items:
            return 0
        self._kinds.append("download")
        for it in items:
            self.queue.submit(TransferTask(it.name, lambda it=it: do_download(self.api, it.id, dest_dir, it.name)))
        return len(items)

    def prepare_for_drag(self, ids: list[str], names: dict[str, str]) -> list[str]:
        """Drag-out: QDrag needs real files before it starts, so download synchronously into a temp dir.
        (Files are small; a blocking fetch inside startDrag is the simple, documented trade-off.)"""
        self.cleanup_drag()
        self._drag_dir = tempfile.mkdtemp(prefix="litedrive-drag-")
        out = []
        for fid in ids:
            out.append(str(do_download(self.api, fid, self._drag_dir, names.get(fid, fid))))
        return out

    def cleanup_drag(self) -> None:
        if self._drag_dir:
            shutil.rmtree(self._drag_dir, ignore_errors=True)
            self._drag_dir = None
