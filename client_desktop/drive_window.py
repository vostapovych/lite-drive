"""DriveWindow: toolbar + table | preview + status bar. Wires controllers; contains no network code."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (QComboBox, QFileDialog, QLabel, QMainWindow, QMenu, QSplitter, QToolBar,
                               QToolButton)

from client_desktop.api_client import ApiClient
from client_desktop.file_list_controller import FileListController
from client_desktop.file_table_view import FileTableView
from client_desktop.models import COLUMNS, FileItem, FileTableModel, FilterMode, ItemRole, NameTypeProxyModel
from client_desktop.preview import PreviewKind
from client_desktop.preview_pane import PreviewPane
from client_desktop.sync_controller import SyncController
from client_desktop.transfers import TransferController, TransferQueue
from client_desktop.view_settings import ViewSettings


class DriveWindow(QMainWindow):
    def __init__(self, api: ApiClient, settings: QSettings, user_email: str = ""):
        super().__init__()
        self.api = api
        self.view_settings = ViewSettings(settings)
        self.setWindowTitle(f"Lite Drive — {user_email}" if user_email else "Lite Drive")
        self.resize(1200, 640)

        self.model = FileTableModel()
        self.proxy = NameTypeProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.table = FileTableView()
        self.table.setModel(self.proxy)
        self.preview = PreviewPane()
        self.files = FileListController(api, self.model, self)
        self.files.dialog_parent = self
        self.queue = TransferQueue(self)
        self.transfers = TransferController(api, self.queue, self)
        self.sync = SyncController(api, self.queue, parent=self)
        self._settings = settings
        # injectable pickers so tests / screenshot scripts can drive the flows without native dialogs
        self.choose_files = lambda: QFileDialog.getOpenFileNames(self, "Upload files")[0]
        self.choose_dir = lambda title: QFileDialog.getExistingDirectory(self, title)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self.table)
        split.addWidget(self.preview)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setSizes([760, 440])
        self.setCentralWidget(split)

        self.status_label = QLabel("")
        self.statusBar().addWidget(self.status_label, 1)
        self._build_toolbar()

        for col, width in enumerate((170, 125, 125, 100)):  # Name, Created, Modified, Uploaded by
            self.table.setColumnWidth(col, width)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.sort_name(Qt.SortOrder.AscendingOrder)
        for col in self.view_settings.hidden_columns():
            self.table.set_column_hidden(col, True)
        self.table.on_column_toggled = self.view_settings.set_hidden
        self.set_filter(self.view_settings.filter_mode())

        self.table.selectionModel().currentRowChanged.connect(lambda cur, _prev: self._on_current(cur))
        self.proxy.layoutChanged.connect(self._update_status)
        self.proxy.modelReset.connect(self._update_status)
        self.proxy.rowsInserted.connect(self._update_status)
        self.proxy.rowsRemoved.connect(self._update_status)
        self._pending_info = ""  # result message to show once the follow-up refresh completes
        self.files.refreshed.connect(self._on_refreshed)
        self.files.deleted.connect(lambda names: setattr(self, "_pending_info", f"Deleted {names}"))
        self.files.failed.connect(lambda msg: self._info(f"Error: {msg}"))
        self.table.horizontalHeader().sortIndicatorChanged.connect(self._sync_sort_actions)

        # transfers: drag in, drag out, buttons
        self.table.filesDropped.connect(self.upload_paths)
        self.table.drag_paths = self._paths_for_drag
        self.transfers.batchFinished.connect(self._on_batch_finished)
        self.queue.taskFailed.connect(lambda label, err: self._info(f"Failed {label}: {err}"))
        # sync
        self.sync.bound.connect(lambda f: (self.lbl_folder.setText(f"Folder: {f}"), self._info("Folder bound")))
        self.sync.synchronised.connect(self._on_synchronised)
        self.sync.failed.connect(lambda msg: self._info(f"Sync error: {msg}"))
        saved = str(settings.value("sync/folder", "") or "")
        if saved and Path(saved).is_dir():
            self.sync.bind(saved)

    # ---- toolbar ----
    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)
        self.toolbar = tb
        self.act_refresh = tb.addAction("Refresh", self.refresh)
        self.act_upload = tb.addAction("Upload…", self.upload_dialog)
        self.act_download = tb.addAction("Download…", self.download_selected)
        self.act_delete = tb.addAction("Delete", self.delete_selected)
        tb.addSeparator()

        grp = QActionGroup(self)
        grp.setExclusive(True)
        self.act_sort_asc = QAction("Name A→Z", self, checkable=True)
        self.act_sort_desc = QAction("Name Z→A", self, checkable=True)
        for a, order in ((self.act_sort_asc, Qt.SortOrder.AscendingOrder), (self.act_sort_desc, Qt.SortOrder.DescendingOrder)):
            grp.addAction(a)
            a.triggered.connect(lambda _=False, o=order: self.sort_name(o))
            tb.addAction(a)
        tb.addSeparator()

        tb.addWidget(QLabel(" Show: "))
        self.filter_combo = QComboBox()
        self.filter_combo.setObjectName("filterCombo")
        self.filter_combo.addItem("All files", FilterMode.ALL)
        self.filter_combo.addItem("Only .cpp and .png", FilterMode.CPP_PNG)
        self.filter_combo.currentIndexChanged.connect(lambda i: self.set_filter(self.filter_combo.itemData(i)))
        tb.addWidget(self.filter_combo)
        tb.addSeparator()

        self.columns_menu = QMenu("Columns", self)
        self.columns_menu.aboutToShow.connect(self._rebuild_columns_menu)
        btn = QToolButton()
        btn.setText("Columns")
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.setMenu(self.columns_menu)
        tb.addWidget(btn)
        tb.addSeparator()

        self.act_bind = tb.addAction("Bind folder…", self.bind_dialog)
        self.act_sync = tb.addAction("Sync now", self.sync.synchronise)
        self.act_auto = QAction("Auto-sync", self, checkable=True)
        self.act_auto.setChecked(True)
        self.act_auto.toggled.connect(lambda on: setattr(self.sync, "auto_sync", on))
        tb.addAction(self.act_auto)
        self.lbl_folder = QLabel("  No folder bound")
        self.lbl_folder.setObjectName("folderLabel")
        tb.addWidget(self.lbl_folder)

    def _rebuild_columns_menu(self) -> None:
        self.columns_menu.clear()
        self.table.build_columns_menu(self.columns_menu)

    # ---- behaviour ----
    def sort_name(self, order: Qt.SortOrder) -> None:
        self.table.sortByColumn(0, order)
        self._sync_sort_actions()

    def _sync_sort_actions(self, *_):
        h = self.table.horizontalHeader()
        on_name = h.sortIndicatorSection() == 0
        asc = h.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
        self.act_sort_asc.setChecked(on_name and asc)
        self.act_sort_desc.setChecked(on_name and not asc)

    def set_filter(self, mode: FilterMode) -> None:
        mode = FilterMode(mode)
        self.proxy.set_filter_mode(mode)
        self.view_settings.set_filter_mode(mode)
        idx = self.filter_combo.findData(mode)
        if idx >= 0 and idx != self.filter_combo.currentIndex():
            self.filter_combo.blockSignals(True)
            self.filter_combo.setCurrentIndex(idx)
            self.filter_combo.blockSignals(False)
        self._update_status()

    def refresh(self) -> None:
        self.files.refresh()

    def selected_items(self) -> list[FileItem]:
        rows = {self.proxy.mapToSource(i).row() for i in self.table.selectionModel().selectedRows()}
        return [self.model.item_at(r) for r in sorted(rows)]

    def delete_selected(self) -> None:
        self.files.delete(self.selected_items())

    # ---- transfers / sync ----
    def upload_dialog(self) -> None:
        paths = self.choose_files()
        if paths:
            self.upload_paths(paths)

    def upload_paths(self, paths: list[str]) -> None:
        n = self.transfers.upload(paths)
        self._info(f"Uploading {n} file(s)…" if n else "Nothing to upload (folders are not supported)")

    def download_selected(self) -> None:
        items = self.selected_items()
        if not items:
            self._info("Select file(s) to download")
            return
        dest = self.choose_dir("Download to…")
        if dest:
            self._info(f"Downloading {self.transfers.download(items, dest)} file(s)…")

    def _paths_for_drag(self, ids: list[str]) -> list[str]:
        names = {i.id: i.name for i in self.model.items()}
        try:
            return self.transfers.prepare_for_drag(ids, names)
        except Exception as exc:  # noqa: BLE001
            self._info(f"Drag failed: {getattr(exc, 'message', exc)}")
            return []

    def _on_refreshed(self, n: int) -> None:
        msg, self._pending_info = self._pending_info, ""
        self._info(msg or f"Loaded {n} file(s)")

    def _on_batch_finished(self, kind: str, ok: int, errors: list) -> None:
        msg = f"{kind.capitalize()} finished: {ok} ok" + (f", {len(errors)} failed" if errors else "")
        if kind == "upload":
            self._pending_info = msg
            self.refresh()
        else:
            self._info(msg)

    def bind_dialog(self) -> None:
        folder = self.choose_dir("Folder to keep in sync")
        if folder:
            self._settings.setValue("sync/folder", folder)
            self.sync.bind(folder)
            self.sync.synchronise()

    def _on_synchronised(self, r: dict) -> None:
        msg = f"Sync: {r['uploaded']} uploaded, {r['downloaded']} downloaded, {r['skipped']} unchanged"
        if r["errors"]:
            msg += f", {len(r['errors'])} failed"
        self.sync_summary = r
        self._pending_info = msg
        self.refresh()

    def closeEvent(self, event) -> None:
        self.sync.watcher.stop()
        self.transfers.cleanup_drag()
        super().closeEvent(event)

    def _on_current(self, cur) -> None:
        if not cur.isValid():
            self.preview.clear()
            return
        item = self.proxy.index(cur.row(), 0).data(ItemRole)
        kind = self.preview.show_file(item.name)
        if kind is not PreviewKind.UNAVAILABLE:
            self.files.load_preview(item, self.preview.render, self.preview.render_error)

    def _info(self, text: str) -> None:
        self._last_info = text
        self._update_status()

    def _update_status(self, *_):
        info = getattr(self, "_last_info", "")
        shown, total = self.proxy.rowCount(), self.model.rowCount()
        self.status_label.setText(f"{shown} of {total} file(s) shown" + (f"   |   {info}" if info else ""))
