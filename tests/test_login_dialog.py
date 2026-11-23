from PySide6.QtWidgets import QDialog

from client_desktop.api_client import ApiClient
from client_desktop.login_dialog import LoginDialog
from client_desktop.session_store import SessionStore
from tests.helpers import wait_until


def make(live_server):
    session = SessionStore()
    api = ApiClient(session, live_server)

    def submit(url, email, pw):
        api.set_base_url(url)
        api.login(email, pw)

    return LoginDialog(submit, live_server, "alice@example.com"), session


def test_bad_password_keeps_dialog_open_and_shows_error(qapp, live_server):
    dlg, session = make(live_server)
    dlg.password.setText("nope")
    dlg.submit()
    assert wait_until(lambda: dlg.buttons.isEnabled() and "Invalid" in dlg.status.text())
    assert dlg.result() != QDialog.DialogCode.Accepted
    assert session.bearer() is None


def test_good_login_accepts_and_stores_token(qapp, live_server):
    dlg, session = make(live_server)
    dlg.password.setText("alice123")
    dlg.submit()
    assert wait_until(lambda: dlg.result() == QDialog.DialogCode.Accepted)
    assert session.bearer()
