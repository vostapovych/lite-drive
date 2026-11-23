"""PreviewPane(show, render): .js -> plain text, .png -> image, anything else -> "Preview unavailable"."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QScrollArea, QStackedWidget

from client_desktop.preview import UNAVAILABLE_TEXT, PreviewKind, preview_kind


class PreviewPane(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.message = QLabel("Select a file to preview")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setObjectName("previewMessage")
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setObjectName("previewText")
        self.image = QLabel()
        self.image.setObjectName("previewImage")
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.image)
        for w in (self.message, self.text, scroll):
            self.addWidget(w)
        self._scroll = scroll
        self.current_name: str | None = None

    def clear(self) -> None:
        self.current_name = None
        self.message.setText("Select a file to preview")
        self.setCurrentWidget(self.message)

    def show_file(self, name: str) -> PreviewKind:
        """Start previewing `name`. Returns its kind; for TEXT/IMAGE the caller then fetches bytes and calls render()."""
        self.current_name = name
        kind = preview_kind(name)
        if kind is PreviewKind.UNAVAILABLE:
            self.message.setText(UNAVAILABLE_TEXT)
            self.setCurrentWidget(self.message)
        else:
            self.message.setText("Loading…")
            self.setCurrentWidget(self.message)
        return kind

    # design name `show` kept as an alias
    show = show_file

    def render(self, name: str, data: bytes) -> None:
        if name != self.current_name:  # stale result for a previously selected file
            return
        kind = preview_kind(name)
        if kind is PreviewKind.TEXT:
            self.text.setPlainText(data.decode("utf-8", errors="replace"))
            self.setCurrentWidget(self.text)
        elif kind is PreviewKind.IMAGE:
            pix = QPixmap()
            if pix.loadFromData(data):
                self.image.setPixmap(pix)
                self.setCurrentWidget(self._scroll)
            else:
                self.message.setText("Image could not be decoded")
                self.setCurrentWidget(self.message)
        else:
            self.message.setText(UNAVAILABLE_TEXT)
            self.setCurrentWidget(self.message)

    def render_error(self, name: str, message: str) -> None:
        if name == self.current_name:
            self.message.setText(f"Preview failed: {message}")
            self.setCurrentWidget(self.message)
