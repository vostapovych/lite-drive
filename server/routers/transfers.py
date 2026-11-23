from fastapi import APIRouter, Depends, HTTPException

from server.deps import CurrentUser, get_file_service, get_transfer_service
from server.models import AuthUser, DownloadUrlOut, ReserveIn, ReserveOut
from server.services import FileService, NotFound, TransferService

router = APIRouter(tags=["transfers"])


@router.post("/uploads", response_model=ReserveOut)
def reserve_upload(
    body: ReserveIn,
    user: AuthUser = Depends(CurrentUser.resolve),
    files: FileService = Depends(get_file_service),
    transfers: TransferService = Depends(get_transfer_service),
):
    try:
        row = files.reserve(user, body)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return ReserveOut(fileId=row.id, uploadUrl=transfers.uploadUrl(row))


@router.get("/files/{file_id}/download-url", response_model=DownloadUrlOut)
def download_url(
    file_id: str,
    user: AuthUser = Depends(CurrentUser.resolve),
    transfers: TransferService = Depends(get_transfer_service),
):
    try:
        url, row = transfers.downloadUrl(user, file_id)
    except NotFound:
        raise HTTPException(404, "File not found")
    return DownloadUrlOut(url=url, name=row.name, modifiedAt=row.modified_at)
