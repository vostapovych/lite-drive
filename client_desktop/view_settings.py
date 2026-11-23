"""ViewSettings: which columns are hidden + chosen filter, persisted in QSettings. Name (col 0) is never hideable."""
from __future__ import annotations

from PySide6.QtCore import QSettings

from client_desktop.models import FilterMode


class ViewSettings:
    def __init__(self, settings: QSettings):
        self._s = settings

    def hidden_columns(self) -> set[int]:
        raw = str(self._s.value("view/hidden", ""))
        return {int(x) for x in raw.split(",") if x.strip().isdigit() and int(x) != 0}

    def set_hidden(self, column: int, hidden: bool) -> None:
        if column == 0:
            return
        cols = self.hidden_columns()
        if hidden:
            cols.add(column)
        else:
            cols.discard(column)
        self._s.setValue("view/hidden", ",".join(map(str, sorted(cols))))

    def filter_mode(self) -> FilterMode:
        try:
            return FilterMode(str(self._s.value("view/filter", FilterMode.ALL.value)))
        except ValueError:
            return FilterMode.ALL

    def set_filter_mode(self, mode: FilterMode) -> None:
        self._s.setValue("view/filter", FilterMode(mode).value)
