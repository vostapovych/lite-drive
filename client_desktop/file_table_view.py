"""FileTableView(filesDropped, rowsDraggedOut). Header right-click toggles columns (Name cannot be hidden)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QMenu, QTableView

from client_desktop.models import COLUMNS


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

    def _header_menu(self, pos) -> None:
        menu = QMenu(self)
        self.build_columns_menu(menu)
        menu.exec(self.horizontalHeader().mapToGlobal(pos))
