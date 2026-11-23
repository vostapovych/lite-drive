"""FolderWatcher(scan, start, changed): lists a bound folder (flat) and watches it with watchdog.
Watchdog callbacks arrive on its own thread; they are marshalled to the GUI thread and debounced."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from client_desktop.sync_planner import LocalFile


class _Handler(FileSystemEventHandler):
    def __init__(self, emit):
        self._emit = emit

    def on_any_event(self, event):
        if not event.is_directory:
            self._emit()


class FolderWatcher(QObject):
    changed = Signal()
    _raw = Signal()

    def __init__(self, parent: QObject | None = None, debounce_ms: int = 700):
        super().__init__(parent)
        self._observer: Observer | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self.changed)
        self._raw.connect(self._timer.start)  # queued across threads, restarts the debounce

    @staticmethod
    def scan(folder: str) -> dict[str, LocalFile]:
        out: dict[str, LocalFile] = {}
        for p in Path(folder).iterdir():
            if p.is_file() and not p.name.startswith("."):
                out[p.name] = LocalFile(p.name, datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc))
        return out

    def start(self, folder: str) -> None:
        self.stop()
        self._observer = Observer()
        self._observer.schedule(_Handler(self._raw.emit), folder, recursive=False)
        self._observer.start()

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None
        self._timer.stop()
