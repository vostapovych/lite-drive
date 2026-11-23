"""Tiny helper: run a blocking function on the global QThreadPool, deliver the result on the GUI thread."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

_alive: set = set()  # keep Worker/signal objects alive until their result is delivered


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(object)


class Worker(QRunnable):
    def __init__(self, fn: Callable[[], Any]):
        super().__init__()
        self.fn = fn
        self.signals = _Signals()
        self.setAutoDelete(False)  # Python owns it (see _alive)

    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as exc:  # noqa: BLE001 - surfaced to the GUI
            self.signals.failed.emit(exc)
        else:
            self.signals.done.emit(result)


def run_async(fn, on_done=None, on_error=None, pool: QThreadPool | None = None) -> Worker:
    w = Worker(fn)
    _alive.add(w)

    def finish(cb):
        def inner(value):
            _alive.discard(w)
            if cb:
                cb(value)
        return inner

    w.signals.done.connect(finish(on_done))
    w.signals.failed.connect(finish(on_error))
    (pool or QThreadPool.globalInstance()).start(w)
    return w
