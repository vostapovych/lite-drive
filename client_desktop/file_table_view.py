"""FileTableView(filesDropped, rowsDraggedOut). Header right-click toggles columns (Name cannot be hidden)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QUrl, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QMenu, QTableView

from client_desktop.models import COLUMNS, ItemRole


class FileTableView(QTableView):
    filesDropped = Signal(list)  # list[str] local paths
    rowsDraggedOut = Signal(list)  # list[str] file ids

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.horizontalHeader().customContextMenuRequested.connect(self._header_menu)
        self.on_column_toggled = None  # callable(column, hidden), set by DriveWindow
        # drag & drop: drop local files in -> filesDropped; drag rows out -> rowsDraggedOut + real files
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.drag_paths = None  # callable(ids: list[str]) -> list[str] local paths; set by DriveWindow

    def set_column_hidden(self, column: int, hidden: bool) -> None:
        if column == 0:
            return  # Name is always visible
        self.setColumnHidden(column, hidden)

    def toggle_column(self, column: int, visible: bool) -> None:
        self.set_column_hidden(column, not visible)
        if self.on_column_toggled:
            self.on_column_toggled(column, not visible)

    def build_columns_menu(self, menu: QMenu) -> None:
        for col, title in enumerate(COLUMNS):
            act = menu.addAction(title)
            act.setCheckable(True)
            act.setChecked(not self.isColumnHidden(col))
            act.setEnabled(col != 0)
            act.toggled.connect(lambda checked, c=col: self.toggle_column(c, checked))

    # ---- drop IN: local files -> upload ----
    @staticmethod
    def local_files(mime) -> list[str]:
        if not mime.hasUrls():
            return []
        return [u.toLocalFile() for u in mime.urls() if u.isLocalFile() and Path(u.toLocalFile()).is_file()]

    def dragEnterEvent(self, event) -> None:
        if self.local_files(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self.local_files(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        paths = self.local_files(event.mimeData())
        if paths:
            event.acceptProposedAction()
            self.filesDropped.emit(paths)
        else:
            event.ignore()

    # ---- drag OUT: rows -> real files in the OS file manager ----
    def selected_ids(self) -> list[str]:
        rows = self.selectionModel().selectedRows()
        return [r.data(ItemRole).id for r in rows]

    @staticmethod
    def make_drag_mime(paths: list[str]) -> QMimeData:
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
        return mime

    def startDrag(self, supportedActions) -> None:
        ids = self.selected_ids()
        if not ids:
            return
        self.rowsDraggedOut.emit(ids)
        if self.drag_paths is None:
            return
        paths = self.drag_paths(ids)  # downloads to a temp dir (blocking; files are small)
        if not paths:
            return
        drag = QDrag(self)
        drag.setMimeData(self.make_drag_mime(paths))
        drag.exec(Qt.DropAction.CopyAction)

    def _header_menu(self, pos) -> None:
        menu = QMenu(self)
        self.build_columns_menu(menu)
        menu.exec(self.horizontalHeader().mapToGlobal(pos))
