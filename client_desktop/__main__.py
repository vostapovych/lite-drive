"""python -m client_desktop  — sign in, then open the drive window."""
import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from client_desktop.api_client import ApiClient
from client_desktop.drive_window import DriveWindow
from client_desktop.login_dialog import LoginDialog
from client_desktop.session_store import SessionStore


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("LiteDrive")
    app.setApplicationName("LiteDriveDesktop")
    settings = QSettings()
    session = SessionStore(settings)
    url, email = session.remembered()
    api = ApiClient(session, url)

    def on_submit(base_url: str, mail: str, password: str) -> None:
        api.set_base_url(base_url)
        api.login(mail, password)

    dlg = LoginDialog(on_submit, url, email)
    if dlg.exec() != LoginDialog.DialogCode.Accepted:
        return 0
    win = DriveWindow(api, settings, session.email)
    win.show()
    win.refresh()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
