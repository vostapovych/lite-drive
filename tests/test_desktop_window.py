"""Desktop shell against a live (fake-backed) server: login, list, columns, sort, filter, preview, delete."""
import pytest
from PySide6.QtCore import QSettings, Qt

from client_desktop.api_client import ApiClient, ApiError
from client_desktop.drive_window import DriveWindow
from client_desktop.models import FilterMode
from client_desktop.session_store import SessionStore
from tests.helpers import wait_until


@pytest.fixture
def window(qapp, live_server, tmp_path):
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    session = SessionStore(settings)
    api = ApiClient(session, live_server)
    api.login("alice@example.com", "alice123")
    w = DriveWindow(api, settings, "alice@example.com")
    w.show()
    w.refresh()
    assert wait_until(lambda: w.model.rowCount() == 7)
    yield w
    w.close()


def names(w):
    return [w.proxy.index(r, 0).data() for r in range(w.proxy.rowCount())]


def test_login_failure_raises(qapp, live_server):
    api = ApiClient(SessionStore(), live_server)
    with pytest.raises(ApiError) as e:
        api.login("alice@example.com", "wrong")
    assert e.value.status == 401


def test_user_sees_only_own_files(window):
    assert "bob-secret.cpp" not in names(window)


def test_default_sort_and_toolbar_sort_both_ways(window):
    assert names(window) == sorted(names(window), key=str.casefold)
    window.act_sort_desc.trigger()
    assert names(window) == sorted(names(window), key=str.casefold, reverse=True)
    assert window.act_sort_desc.isChecked()
    window.act_sort_asc.trigger()
    assert names(window)[0] == "apple.cpp"


def test_filter_combo(window):
    window.filter_combo.setCurrentIndex(1)
    assert set(names(window)) == {"apple.cpp", "Banner.PNG", "logo.png", "main.cpp"}
    window.filter_combo.setCurrentIndex(0)
    assert len(names(window)) == 7


def test_columns_hideable_except_name(window):
    for col in (1, 2, 3, 4):
        window.table.toggle_column(col, False)
        assert window.table.isColumnHidden(col)
    window.table.toggle_column(0, False)
    assert not window.table.isColumnHidden(0)
    assert window.view_settings.hidden_columns() == {1, 2, 3, 4}
    window.table.toggle_column(2, True)
    assert not window.table.isColumnHidden(2)


def select(w, name):
    r = names(w).index(name)
    w.table.selectRow(r)
    w.table.setCurrentIndex(w.proxy.index(r, 0))


def test_preview_js_png_and_unavailable(window):
    select(window, "hello.js")
    assert wait_until(lambda: window.preview.currentWidget() is window.preview.text)
    assert "function hello" in window.preview.text.toPlainText()
    select(window, "logo.png")
    assert wait_until(lambda: window.preview.image.pixmap() is not None and not window.preview.image.pixmap().isNull())
    select(window, "main.cpp")
    assert window.preview.message.text() == "Preview unavailable"
    assert window.preview.currentWidget() is window.preview.message


def test_delete_requires_confirmation(window):
    select(window, "zeta.md")
    window.files.confirm = lambda parent, text: False  # user cancels
    window.delete_selected()
    wait_until(lambda: False, 0.3)
    assert "zeta.md" in names(window)
    asked = []
    window.files.confirm = lambda parent, text: asked.append(text) or True
    window.delete_selected()
    assert wait_until(lambda: "zeta.md" not in names(window))
    assert "zeta.md" in asked[0]
