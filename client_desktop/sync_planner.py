"""SyncPlanner: PURE decision logic (no I/O, no Qt). Rules:
- newer modifiedAt wins (local newer -> UPLOAD, remote newer -> DOWNLOAD)
- equal modifiedAt -> SKIP
- present on one side only -> copy to the other side
- NEVER delete anything, on either side
Timestamps compare at whole-second resolution (the server stores seconds)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class SyncKind(str, Enum):
    UPLOAD = "upload"
    DOWNLOAD = "download"
    SKIP = "skip"


@dataclass(frozen=True)
class LocalFile:
    name: str
    modified_at: datetime


@dataclass(frozen=True)
class RemoteFile:
    id: str
    name: str
    modified_at: datetime


@dataclass(frozen=True)
class SyncAction:
    kind: SyncKind
    name: str
    remote_id: str | None = None
    remote_modified_at: datetime | None = None
    local_modified_at: datetime | None = None


def _secs(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


class SyncPlanner:
    def plan(self, binding: str, local: dict[str, LocalFile], remote: dict[str, RemoteFile]) -> list[SyncAction]:
        """`binding` identifies the bound folder (kept for the approved signature; not touched here)."""
        actions: list[SyncAction] = []
        for name in sorted(set(local) | set(remote), key=str.casefold):
            lo, re_ = local.get(name), remote.get(name)
            if lo and not re_:
                actions.append(SyncAction(SyncKind.UPLOAD, name, local_modified_at=lo.modified_at))
            elif re_ and not lo:
                actions.append(SyncAction(SyncKind.DOWNLOAD, name, re_.id, re_.modified_at))
            else:
                l, r = _secs(lo.modified_at), _secs(re_.modified_at)
                if l > r:
                    actions.append(SyncAction(SyncKind.UPLOAD, name, re_.id, re_.modified_at, lo.modified_at))
                elif r > l:
                    actions.append(SyncAction(SyncKind.DOWNLOAD, name, re_.id, re_.modified_at, lo.modified_at))
                else:
                    actions.append(SyncAction(SyncKind.SKIP, name, re_.id, re_.modified_at, lo.modified_at))
        return actions
