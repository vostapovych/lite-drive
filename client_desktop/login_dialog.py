"""LoginDialog(exec, onSubmit). onSubmit(base_url, email, password) runs on a worker thread and raises on failure;
the dialog stays open and shows the error, or accepts on success."""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout)

from client_desktop.workers import run_async


class LoginDialog(QDialog):
    def __init__(self, on_submit: Callable[[str, str, str], None], base_url: str = "", email: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lite Drive — Sign in")
        self.setMinimumWidth(380)
        self.onSubmit = on_submit
        self.url = QLineEdit(base_url)
        self.url.setObjectName("serverUrl")
        self.email = QLineEdit(email)
        self.email.setObjectName("email")
        self.password = QLineEdit()
        self.password.setObjectName("password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.status = QLabel("")
        self.status.setObjectName("loginStatus")
        self.status.setWordWrap(True)
        form = QFormLayout()
        form.addRow("Server", self.url)
        form.addRow("Email", self.email)
        form.addRow("Password", self.password)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Sign in")
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.status)
        lay.addWidget(self.buttons)

    def set_error(self, text: str) -> None:
        self.status.setStyleSheet("color: #b00020;")
        self.status.setText(text)

    def submit(self) -> None:
        url, email, pw = self.url.text().strip(), self.email.text().strip(), self.password.text()
        if not (url and email and pw):
            self.set_error("Enter server, email and password.")
            return
        self.buttons.setEnabled(False)
        self.status.setStyleSheet("")
        self.status.setText("Signing in… (a free Render server can take up to a minute to wake up)")

        def failed(exc):
            self.buttons.setEnabled(True)
            self.set_error(getattr(exc, "message", str(exc)))

        def done(_):
            self.accept()

        run_async(lambda: self.onSubmit(url, email, pw), done, failed)
