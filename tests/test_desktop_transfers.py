"""Upload / download / drag-and-drop / sync, end to end against a live fake-backed server."""
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPointF, QSettings, Qt, QUrl
from PySide6.QtGui import QDropEvent

from client_desktop.api_client import ApiClient
from client_desktop.drive_window import DriveWindow
from client_desktop.session_store import SessionStore
from tests.helpers import wait_until


@pytest.fixture
def window(qapp, live_server, tmp_path):
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    api = ApiClient(SessionStore(settings), live_server)
    api.login("alice@example.com", "alice123")
    w = DriveWindow(api, settings, "alice@example.com")
    w.act_auto.setChecked(False)  # deterministic: no watcher-triggered syncs unless a test wants them
    w.show()
    w.refresh()
    assert wait_until(lambda: w.model.rowCount() == 7)
    yield w
    w.close()


def names(w):
    return {w.model.item_at(r).name for r in range(w.model.rowCount())}


def item(w, name):
    return next(i for i in w.model.items() if i.name == name)


def server_bytes(sb, w, name):
    row = next(r for r in sb.rows.values() if r.name == name and r.owner_id == sb.users["alice@example.com"].id)
    return sb.blobs[row.storage_path]


def set_mtime(path, dt):
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


def test_upload_dialog_ignores_folders(window, sb, tmp_path):
    f = tmp_path / "up.js"
    f.write_text("console.log(1)")
    d = tmp_path / "adir"
    d.mkdir()
    window.choose_files = lambda: [str(f), str(d)]
    window.upload_dialog()
    assert wait_until(lambda: "up.js" in names(window))
    assert server_bytes(sb, window, "up.js") == b"console.log(1)"
    assert "adir" not in names(window)


def test_drop_files_onto_table_uploads_them(window, sb, tmp_path):
    f1, f2 = tmp_path / "dropped1.png", tmp_path / "dropped2.cpp"
    f1.write_bytes(b"\x89PNGfake")
    f2.write_text("int x;")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(f1)), QUrl.fromLocalFile(str(f2))])
    ev = QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.table.dropEvent(ev)
    assert ev.isAccepted()
    assert wait_until(lambda: {"dropped1.png", "dropped2.cpp"} <= names(window))
    assert server_bytes(sb, window, "dropped2.cpp") == b"int x;"


def test_non_file_drop_is_rejected(window):
    mime = QMimeData()
    mime.setText("just text")
    ev = QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.table.dropEvent(ev)
    assert not ev.isAccepted()


def test_download_selected_sets_local_mtime_to_server_value(window, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    it = item(window, "hello.js")
    window.table.selectRow(next(r for r in range(window.proxy.rowCount()) if window.proxy.index(r, 0).data() == "hello.js"))
    window.choose_dir = lambda title: str(out)
    window.download_selected()
    assert wait_until(lambda: (out / "hello.js").exists() and "finished" in window.status_label.text())
    assert b"function hello" in (out / "hello.js").read_bytes()
    assert int((out / "hello.js").stat().st_mtime) == int(it.modified.timestamp())


def test_drag_out_prepares_real_files(window):
    ids = [item(window, "hello.js").id, item(window, "logo.png").id]
    paths = window._paths_for_drag(ids)
    assert sorted(Path(p).name for p in paths) == ["hello.js", "logo.png"]
    assert all(Path(p).stat().st_size > 0 for p in paths)
    mime = window.table.make_drag_mime(paths)
    assert [Path(u.toLocalFile()).name for u in mime.urls()] == [Path(p).name for p in paths]
    window.transfers.cleanup_drag()
    assert not Path(paths[0]).exists()


def run_sync(window, timeout=15):
    results = []
    window.sync.synchronised.connect(results.append)
    window.sync.synchronise()
    assert wait_until(lambda: len(results) == 1, timeout), "sync did not finish"
    return results[0]


def test_sync_follows_planner_rules_and_never_deletes(window, sb, tmp_path):
    folder = tmp_path / "bound"
    folder.mkdir()
    newer = datetime(2026, 11, 22, tzinfo=timezone.utc)
    older = datetime(2026, 11, 1, tzinfo=timezone.utc)
    (folder / "hello.js").write_text("// local edit, newer")  # newer than server -> UPLOAD
    set_mtime(folder / "hello.js", newer)
    (folder / "main.cpp").write_text("// stale local copy")  # older than server -> DOWNLOAD (overwrites)
    set_mtime(folder / "main.cpp", older)
    (folder / "local_only.txt").write_text("only here")  # not on server -> UPLOAD
    set_mtime(folder / "local_only.txt", older)
    remote_before = set(names(window))

    window.sync.bind(str(folder))
    r = run_sync(window)

    assert r["errors"] == []
    assert r["uploaded"] == 2  # hello.js, local_only.txt
    assert r["downloaded"] == 6  # main.cpp + 5 remote-only
    assert server_bytes(sb, window, "hello.js") == b"// local edit, newer"
    assert server_bytes(sb, window, "local_only.txt") == b"only here"
    assert (folder / "main.cpp").read_text().startswith("#include <iostream>")
    # downloaded file's local mtime == server's value
    remote = {f["name"]: f for f in window.api.listFiles()}
    assert int((folder / "main.cpp").stat().st_mtime) == int(datetime.fromisoformat(remote["main.cpp"]["modifiedAt"]).timestamp())
    # and an uploaded file's server modifiedAt == the local mtime we sent
    assert int(datetime.fromisoformat(remote["hello.js"]["modifiedAt"]).timestamp()) == int(newer.timestamp())
    # NEVER deletes: every remote name still exists, every local file still exists
    assert wait_until(lambda: remote_before | {"local_only.txt"} <= names(window))
    assert {p.name for p in folder.iterdir()} >= {"hello.js", "main.cpp", "local_only.txt", "Notes.txt", "zeta.md"}


def test_second_sync_is_idempotent(window, tmp_path):
    folder = tmp_path / "bound"
    folder.mkdir()
    (folder / "extra.js").write_text("x")
    window.sync.bind(str(folder))
    first = run_sync(window)
    assert first["uploaded"] == 1 and first["downloaded"] == 7
    second = run_sync(window)
    assert (second["uploaded"], second["downloaded"], second["errors"]) == (0, 0, [])
    assert second["skipped"] == 8


def test_watcher_auto_syncs_new_local_file(window, sb, tmp_path):
    folder = tmp_path / "bound"
    folder.mkdir()
    window.sync.bind(str(folder))
    run_sync(window)  # initial pull
    window.act_auto.setChecked(True)
    results = []
    window.sync.synchronised.connect(results.append)
    (folder / "auto.js").write_text("auto")
    assert wait_until(lambda: any(r["uploaded"] >= 1 for r in results), 15)
    assert server_bytes(sb, window, "auto.js") == b"auto"
