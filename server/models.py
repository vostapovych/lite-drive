"""FileRow = what the `files` table stores. FileOut = what the API returns. DTOs for requests."""
from datetime import datetime

from pydantic import BaseModel, Field


class AuthUser(BaseModel):
    id: str
    email: str = ""


class FileRow(BaseModel):
    id: str
    owner_id: str
    name: str
    storage_path: str
    size: int = 0
    created_at: datetime
    modified_at: datetime
    uploaded_by: str
    last_edited_by: str
    committed: bool = False


class FileOut(BaseModel):
    id: str
    name: str
    size: int
    createdAt: datetime
    modifiedAt: datetime
    uploadedBy: str
    lastEditedBy: str


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    userId: str
    email: str


class ReserveIn(BaseModel):
    # NOTE: deliberately no owner field — owner comes from the verified token.
    name: str = Field(min_length=1, max_length=255)
    size: int = Field(default=0, ge=0)


class ReserveOut(BaseModel):
    fileId: str
    uploadUrl: str
    method: str = "PUT"


class CommitIn(BaseModel):
    # Optional client mtime, so a sync upload converges (server modifiedAt == local mtime -> next plan SKIPs).
    modifiedAt: datetime | None = None
    size: int | None = Field(default=None, ge=0)


class DownloadUrlOut(BaseModel):
    url: str
    name: str
    modifiedAt: datetime
