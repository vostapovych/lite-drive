"""FileItem + FileTableModel (source model) and NameTypeProxyModel (client-side sort/filter)."""
from __future__ import annotations

import posixpath
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt

COLUMNS = ["Name", "Created", "Modified", "Uploaded by", "Last edited by"]
ItemRole = Qt.ItemDataRole.UserRole + 1


@dataclass
class FileItem:
    id: str
    name: str
    size: int
    created: datetime
    modified: datetime
    uploaded_by: str
    last_edited_by: str

    @staticmethod
    def from_api(d: dict) -> "FileItem":
        return FileItem(d["id"], d["name"], d.get("size", 0), datetime.fromisoformat(d["createdAt"]),
                        datetime.fromisoformat(d["modifiedAt"]), d["uploadedBy"], d["lastEditedBy"])


def fmt_dt(dt: datetime) -> str:
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


class FileTableModel(QAbstractTableModel):
    def __init__(self, items: list[FileItem] | None = None, parent=None):
        super().__init__(parent)
        self._items: list[FileItem] = list(items or [])

    def set_items(self, items: list[FileItem]) -> None:
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def items(self) -> list[FileItem]:
        return list(self._items)

    def item_at(self, row: int) -> FileItem:
        return self._items[row]

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        it = self._items[index.row()]
        if role == ItemRole:
            return it
        if role == Qt.ItemDataRole.DisplayRole:
            return [it.name, fmt_dt(it.created), fmt_dt(it.modified), it.uploaded_by, it.last_edited_by][index.column()]
        if role == Qt.ItemDataRole.EditRole:  # raw sort value
            return [it.name, it.created, it.modified, it.uploaded_by, it.last_edited_by][index.column()]
        return None


class FilterMode(str, Enum):
    ALL = "all"
    CPP_PNG = "cpp_png"


class NameTypeProxyModel(QSortFilterProxyModel):
    """Variant operations (6): case-insensitive name sort + 'All' / 'only .cpp and .png' filter."""

    ALLOWED = (".cpp", ".png")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = FilterMode.ALL
        self.setSortRole(Qt.ItemDataRole.EditRole)

    def filter_mode(self) -> FilterMode:
        return self._mode

    def set_filter_mode(self, mode: FilterMode) -> None:
        if hasattr(self, "beginFilterChange"):  # Qt >= 6.9; invalidateFilter() is deprecated there
            self.beginFilterChange()
            self._mode = FilterMode(mode)
            self.endFilterChange()
        else:
            self._mode = FilterMode(mode)
            self.invalidateFilter()

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        a, b = left.data(Qt.ItemDataRole.EditRole), right.data(Qt.ItemDataRole.EditRole)
        if left.column() == 0:
            return (a.casefold(), a) < (b.casefold(), b)  # case-insensitive; raw name only breaks exact ties
        if isinstance(a, str):
            return a.casefold() < b.casefold()
        return a < b

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if self._mode is FilterMode.ALL:
            return True
        name = self.sourceModel().index(source_row, 0, source_parent).data(Qt.ItemDataRole.EditRole)
        return posixpath.splitext(name)[1].lower() in self.ALLOWED
