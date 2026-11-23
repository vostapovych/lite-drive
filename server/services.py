"""Business logic. Routers stay thin; services never trust an owner from the request body."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from server.models import AuthUser, CommitIn, FileOut, FileRow, ReserveIn, TokenOut
from server.supabase_client import SupabaseClient, SupabaseError, utcnow


class NotFound(Exception):
    pass


class AuthService:
    def __init__(self, sb: SupabaseClient):
        self.sb = sb

    def login(self, email: str, password: str) -> TokenOut:
        token, user = self.sb.signIn(email, password)
        return TokenOut(accessToken=token, userId=user.id, email=user.email)

    def verify(self, token: str) -> AuthUser:
        return self.sb.verifyJwt(token)

    def logout(self, token: str) -> None:
        self.sb.signOut(token)


class FileService:
    def __init__(self, sb: SupabaseClient):
        self.sb = sb

    def _out(self, rows: list[FileRow]) -> list[FileOut]:
        names = self.sb.userNames({r.uploaded_by for r in rows} | {r.last_edited_by for r in rows})
        return [
            FileOut(
                id=r.id, name=r.name, size=r.size, createdAt=r.created_at, modifiedAt=r.modified_at,
                uploadedBy=names.get(r.uploaded_by, r.uploaded_by),
                lastEditedBy=names.get(r.last_edited_by, r.last_edited_by),
            )
            for r in rows
        ]

    def list(self, user: AuthUser) -> list[FileOut]:
        rows = [r for r in self.sb.listRows(user.id) if r.committed]
        return self._out(sorted(rows, key=lambda r: r.name.casefold()))

    def get(self, user: AuthUser, file_id: str) -> FileRow:
        row = self.sb.getRow(user.id, file_id)
        if row is None:
            raise NotFound(file_id)
        return row

    def reserve(self, user: AuthUser, req: ReserveIn) -> FileRow:
        """Phase 1 of upload. Same name for the same owner = overwrite (reuse the row)."""
        name = req.name.strip().replace("\\", "/").split("/")[-1]  # flat drive: no folders
        if not name:
            raise ValueError("empty file name")
        existing = self.sb.getRowByName(user.id, name)
        if existing:
            return existing
        fid = str(uuid.uuid4())
        now = utcnow()
        row = FileRow(
            id=fid, owner_id=user.id, name=name, storage_path=f"{user.id}/{fid}", size=req.size,
            created_at=now, modified_at=now, uploaded_by=user.id, last_edited_by=user.id, committed=False,
        )
        return self.sb.insertRow(row)

    def commit(self, user: AuthUser, file_id: str, req: CommitIn) -> FileOut:
        """Phase 3 of upload (after the client PUT the bytes to the signed URL)."""
        row = self.get(user, file_id)
        modified = req.modifiedAt or utcnow()
        if modified.tzinfo is None:
            modified = modified.replace(tzinfo=timezone.utc)
        changes = {"committed": True, "modified_at": modified, "last_edited_by": user.id}
        if req.size is not None:
            changes["size"] = req.size
        updated = self.sb.updateRow(user.id, row.id, changes)
        if updated is None:
            raise NotFound(file_id)
        return self._out([updated])[0]

    def delete(self, user: AuthUser, file_id: str) -> None:
        row = self.get(user, file_id)
        try:
            self.sb.removeObject(row.storage_path)
        except SupabaseError:
            pass  # object may never have been uploaded; the row is what the user sees
        self.sb.deleteRow(user.id, row.id)


class TransferService:
    def __init__(self, sb: SupabaseClient, files: FileService):
        self.sb = sb
        self.files = files

    def uploadUrl(self, row: FileRow) -> str:
        return self.sb.signUpload(row.storage_path)

    def downloadUrl(self, user: AuthUser, file_id: str) -> tuple[str, FileRow]:
        row = self.files.get(user, file_id)
        if not row.committed:
            raise NotFound(file_id)
        return self.sb.signDownload(row.storage_path, row.name), row


def as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
