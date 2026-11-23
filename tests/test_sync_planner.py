"""Test 3: SyncPlanner rules, including never-delete."""
from datetime import datetime, timedelta, timezone

from client_desktop.sync_planner import LocalFile, RemoteFile, SyncKind, SyncPlanner

T = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
plan = SyncPlanner().plan


def kinds(actions):
    return {a.name: a.kind for a in actions}


def test_local_newer_uploads_remote_newer_downloads_equal_skips():
    local = {n: LocalFile(n, t) for n, t in
             {"a": T + timedelta(minutes=5), "b": T, "c": T}.items()}
    remote = {"a": RemoteFile("1", "a", T), "b": RemoteFile("2", "b", T + timedelta(minutes=5)),
              "c": RemoteFile("3", "c", T)}
    assert kinds(plan("/x", local, remote)) == {"a": SyncKind.UPLOAD, "b": SyncKind.DOWNLOAD, "c": SyncKind.SKIP}


def test_one_sided_files_are_copied_across():
    got = kinds(plan("/x", {"only_local": LocalFile("only_local", T)}, {"only_remote": RemoteFile("9", "only_remote", T)}))
    assert got == {"only_local": SyncKind.UPLOAD, "only_remote": SyncKind.DOWNLOAD}


def test_never_deletes_anything():
    local = {"gone_remote": LocalFile("gone_remote", T)}
    remote = {"gone_local": RemoteFile("1", "gone_local", T)}
    actions = plan("/x", local, remote)
    assert {a.kind for a in actions} <= {SyncKind.UPLOAD, SyncKind.DOWNLOAD, SyncKind.SKIP}
    assert not any("delete" in a.kind.value for a in actions)
    assert {a.name for a in actions} == {"gone_remote", "gone_local"}  # every file still accounted for


def test_sub_second_difference_is_equal():
    local = {"a": LocalFile("a", T + timedelta(milliseconds=400))}
    remote = {"a": RemoteFile("1", "a", T)}
    assert kinds(plan("/x", local, remote)) == {"a": SyncKind.SKIP}


def test_empty_both_sides():
    assert plan("/x", {}, {}) == []
