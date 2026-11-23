"""Desktop screenshots: the REAL window against FakeSupabase with seeded demo data, saved with widget.grab().

    .venv/Scripts/python tools/make_screenshots.py [--offscreen] [--out screenshots/desktop]

Static grabs cannot show an in-flight OS drag, so the drag-and-drop shot is taken right after a real drop event
has been delivered to the table (rows appear, status bar reports the upload)."""
import argparse
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--offscreen", action="store_true", help="use Qt's offscreen platform (no visible windows)")
ap.add_argument("--out", default="screenshots/desktop")
args = ap.parse_args()

import os  # noqa: E402

if args.offscreen:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.demo_server import start_demo_server  # noqa: E402  (also sets LITEDRIVE_FAKE_SUPABASE=1)

from PySide6.QtCore import QMimeData, QPointF, QSettings, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDropEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from client_desktop.api_client import ApiClient  # noqa: E402
from client_desktop.drive_window import DriveWindow  # noqa: E402
from client_desktop.file_list_controller import build_confirm_box  # noqa: E402
from client_desktop.login_dialog import LoginDialog  # noqa: E402
from client_desktop.models import FilterMode  # noqa: E402
from client_desktop.session_store import SessionStore  # noqa: E402

out = Path(args.out)
shutil.rmtree(out, ignore_errors=True)
out.mkdir(parents=True, exist_ok=True)
app = QApplication([])
tmp = Path(tempfile.mkdtemp(prefix="litedrive-shots-"))
n = 0
index: list[str] = []


def pump(ms: int = 150) -> None:
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def wait(cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            pump(120)
            return
        time.sleep(0.01)
    raise TimeoutError("condition not met while taking screenshots")


def shot(widget, name: str, caption: str) -> None:
    global n
    n += 1
    pump(120)
    fname = f"{n:02d}-{name}.png"
    assert widget.grab().save(str(out / fname)), fname
    index.append(f"- `{fname}` — {caption}")
    print("saved", fname)


url, sb, stop = start_demo_server()
settings = QSettings(str(tmp / "settings.ini"), QSettings.Format.IniFormat)
session = SessionStore(settings)
api = ApiClient(session, url)


def on_submit(base_url, email, pw):
    api.set_base_url(base_url)
    api.login(email, pw)


# --- login (+ failed login) ---
dlg = LoginDialog(on_submit, url, "alice@example.com")
dlg.password.setText("wrong-password")
dlg.show()
shot(dlg, "login", "Login dialog")
dlg.submit()
wait(lambda: dlg.buttons.isEnabled() and "Invalid" in dlg.status.text())
shot(dlg, "login-error", "Login rejected by the server")
dlg.password.setText("alice123")
dlg.submit()
wait(lambda: session.bearer() is not None)
dlg.close()

# --- main window ---
w = DriveWindow(api, settings, "alice@example.com")
w.act_auto.setChecked(False)
w.show()
w.refresh()
wait(lambda: w.model.rowCount() == 7)
shot(w, "file-list", "File list (only Alice's files; Bob's are never returned)")

w.act_sort_asc.trigger()
shot(w, "sort-az", "Sorted by name A→Z (case-insensitive)")
w.act_sort_desc.trigger()
shot(w, "sort-za", "Sorted by name Z→A (case-insensitive)")
w.act_sort_asc.trigger()

w.filter_combo.setCurrentIndex(1)
shot(w, "filter-cpp-png", "Filter: only .cpp and .png")
w.filter_combo.setCurrentIndex(0)
shot(w, "filter-all", "Filter: all files")


def select(name):
    for r in range(w.proxy.rowCount()):
        if w.proxy.index(r, 0).data() == name:
            w.table.selectRow(r)
            w.table.setCurrentIndex(w.proxy.index(r, 0))
            return
    raise KeyError(name)


select("hello.js")
wait(lambda: w.preview.currentWidget() is w.preview.text)
shot(w, "preview-js", "Preview: .js shown as plain text")
select("logo.png")
wait(lambda: w.preview.image.pixmap() is not None and not w.preview.image.pixmap().isNull())
shot(w, "preview-png", "Preview: .png shown as an image")
select("main.cpp")
shot(w, "preview-unavailable", "Preview: any other type shows “Preview unavailable”")

w._rebuild_columns_menu()
w.columns_menu.popup(w.mapToGlobal(w.toolbar.pos()) + w.toolbar.rect().center())
pump(200)
shot(w.columns_menu, "columns-menu", "Columns menu (Name is locked on)")
w.columns_menu.hide()
w.table.toggle_column(1, False)
w.table.toggle_column(4, False)
shot(w, "columns-hidden", "“Created” and “Last edited by” hidden")
w.table.toggle_column(1, True)
w.table.toggle_column(4, True)

# --- upload (button path, picker injected) ---
up = tmp / "upload"
up.mkdir()
(up / "report.js").write_text("// uploaded from the toolbar\nexport const answer = 42;\n")
w.choose_files = lambda: [str(up / "report.js")]
w.upload_dialog()
wait(lambda: any(i.name == "report.js" for i in w.model.items()))
select("report.js")
wait(lambda: w.preview.currentWidget() is w.preview.text)
shot(w, "upload", "After Upload…: report.js is listed and previewable")

# --- drag-and-drop in ---
(up / "dropped.cpp").write_text("int dropped() { return 1; }\n")
(up / "dropped.png").write_bytes(sb.blobs[next(r.storage_path for r in sb.rows.values() if r.name == "logo.png")])
mime = QMimeData()
mime.setUrls([QUrl.fromLocalFile(str(up / "dropped.cpp")), QUrl.fromLocalFile(str(up / "dropped.png"))])
w.table.dropEvent(QDropEvent(QPointF(40, 40), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                             Qt.KeyboardModifier.NoModifier))
wait(lambda: {"dropped.cpp", "dropped.png"} <= {i.name for i in w.model.items()})
shot(w, "drag-and-drop-upload", "Two files dropped onto the table were uploaded")

# --- download ---
dl = tmp / "downloads"
dl.mkdir()
select("hello.js")
w.choose_dir = lambda title: str(dl)
w.download_selected()
wait(lambda: (dl / "hello.js").exists() and "Download finished" in w.status_label.text())
shot(w, "download", f"Download finished: hello.js saved to a chosen folder (mtime = server value)")

# --- delete with confirmation ---
select("zeta.md")
box = build_confirm_box(w, "Delete “zeta.md” from your drive?\nThis cannot be undone.")
box.show()
pump(250)
shot(box, "delete-confirmation", "Delete asks for confirmation (Cancel is the default)")
box.close()
w.files.confirm = lambda parent, text: True
w.delete_selected()
wait(lambda: "zeta.md" not in {i.name for i in w.model.items()})
shot(w, "delete-done", "After confirming: zeta.md is gone")

# --- sync ---
sync = tmp / "sync-folder"
sync.mkdir()
(sync / "hello.js").write_text("// newer local edit wins\n")  # newer than server -> upload
(sync / "local-only.txt").write_text("only on this machine\n")  # missing remotely -> upload
(sync / "main.cpp").write_text("// stale local copy\n")  # older than server -> download
old = datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp()
os.utime(sync / "main.cpp", (old, old))
w.sync.bind(str(sync))
results = []
w.sync.synchronised.connect(results.append)
w.sync.synchronise()
wait(lambda: results)
wait(lambda: "Sync:" in w.status_label.text() and w.model.rowCount() >= 9)
shot(w, "sync-result", f"Sync result: {results[0]['uploaded']} uploaded, {results[0]['downloaded']} downloaded, "
                       f"{results[0]['skipped']} unchanged — nothing deleted")
again = []
w.sync.synchronised.connect(again.append)
w.sync.synchronise()
wait(lambda: again)
wait(lambda: "0 uploaded, 0 downloaded" in w.status_label.text())
shot(w, "sync-idempotent", "Second sync: everything unchanged")

(out / "README.md").write_text("# Desktop screenshots (generated by tools/make_screenshots.py)\n\n" + "\n".join(index) + "\n",
                               encoding="utf-8")
w.close()
stop()
shutil.rmtree(tmp, ignore_errors=True)
print(f"done: {n} screenshots in {out}")
