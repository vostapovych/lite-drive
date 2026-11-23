import time

from PySide6.QtWidgets import QApplication


def wait_until(cond, timeout: float = 8.0) -> bool:
    """Pump the Qt event loop until cond() is true (worker results arrive via queued signals)."""
    end = time.time() + timeout
    while time.time() < end:
        QApplication.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    QApplication.processEvents()
    return cond()
