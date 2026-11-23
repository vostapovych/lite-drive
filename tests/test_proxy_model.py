"""Tests 1 and 2: case-insensitive name sort A-Z / Z-A, and the .cpp/.png filter vs all files."""
from datetime import datetime, timezone

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from client_desktop.models import FileItem, FileTableModel, FilterMode, NameTypeProxyModel

NAMES = ["banana.js", "Apple.cpp", "cherry.PNG", "apple2.txt", "Zebra.png", "alpha.CPP", "notes.md", "Beta.js"]


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def proxy(qapp):
    t = datetime(2026, 11, 20, tzinfo=timezone.utc)
    items = [FileItem(str(i), n, 1, t, t, "alice", "alice") for i, n in enumerate(NAMES)]
    src = FileTableModel(items)
    p = NameTypeProxyModel()
    p.setSourceModel(src)
    p._src = src  # keep alive
    return p


def shown(p) -> list[str]:
    return [p.index(r, 0).data(Qt.ItemDataRole.DisplayRole) for r in range(p.rowCount())]


def test_sort_name_ascending_case_insensitive(proxy):
    proxy.sort(0, Qt.SortOrder.AscendingOrder)
    assert shown(proxy) == sorted(NAMES, key=str.casefold)
    assert shown(proxy)[:3] == ["alpha.CPP", "Apple.cpp", "apple2.txt"]  # not ASCII order (Apple < alpha)


def test_sort_name_descending_case_insensitive(proxy):
    proxy.sort(0, Qt.SortOrder.DescendingOrder)
    assert shown(proxy) == sorted(NAMES, key=str.casefold, reverse=True)
    assert shown(proxy)[0] == "Zebra.png"


def test_filter_only_cpp_and_png(proxy):
    proxy.set_filter_mode(FilterMode.CPP_PNG)
    proxy.sort(0, Qt.SortOrder.AscendingOrder)
    assert shown(proxy) == ["alpha.CPP", "Apple.cpp", "cherry.PNG", "Zebra.png"]


def test_filter_all_files_restores_everything(proxy):
    proxy.set_filter_mode(FilterMode.CPP_PNG)
    assert proxy.rowCount() == 4
    proxy.set_filter_mode(FilterMode.ALL)
    assert proxy.rowCount() == len(NAMES)


def test_filter_and_sort_combine(proxy):
    proxy.set_filter_mode(FilterMode.CPP_PNG)
    proxy.sort(0, Qt.SortOrder.DescendingOrder)
    assert shown(proxy) == ["Zebra.png", "cherry.PNG", "Apple.cpp", "alpha.CPP"]
