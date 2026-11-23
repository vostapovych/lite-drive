from fastapi import APIRouter, Depends, HTTPException

from server.deps import CurrentUser, get_file_service
from server.models import AuthUser, CommitIn, FileOut
from server.services import FileService, NotFound

router = APIRouter(prefix="/files", tags=["files"])


@router.get("", response_model=list[FileOut])
def list_files(user: AuthUser = Depends(CurrentUser.resolve), files: FileService = Depends(get_file_service)):
    return files.list(user)


@router.post("/{file_id}/commit", response_model=FileOut)
def commit(
    file_id: str,
    body: CommitIn | None = None,
    user: AuthUser = Depends(CurrentUser.resolve),
    files: FileService = Depends(get_file_service),
):
    try:
        return files.commit(user, file_id, body or CommitIn())
    except NotFound:
        raise HTTPException(404, "File not found")


@router.delete("/{file_id}", status_code=204)
def delete(file_id: str, user: AuthUser = Depends(CurrentUser.resolve), files: FileService = Depends(get_file_service)):
    try:
        files.delete(user, file_id)
    except NotFound:
        raise HTTPException(404, "File not found")
