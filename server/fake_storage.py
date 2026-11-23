"""DEV/TEST ONLY: stands in for Supabase Storage's signed-URL endpoints when FakeSupabase is active.
Bytes live in FakeSupabase memory — never on disk. Not part of the client-facing API."""
from fastapi import APIRouter, HTTPException, Request, Response

router = APIRouter(prefix="/_fake_storage", tags=["fake-storage"], include_in_schema=False)


@router.put("/upload/{token}")
async def put_object(token: str, request: Request):
    sb = request.app.state.sb
    path = sb.resolve_signed(token, "upload")
    if path is None:
        raise HTTPException(403, "Signed URL invalid or expired")
    data = await request.body()
    with sb._lock:
        sb.blobs[path] = data
    return {"Key": path}


@router.get("/object/{token}")
def get_object(token: str, request: Request):
    sb = request.app.state.sb
    path = sb.resolve_signed(token, "download")
    if path is None:
        raise HTTPException(403, "Signed URL invalid or expired")
    with sb._lock:
        data = sb.blobs.get(path)
    if data is None:
        raise HTTPException(404, "Object not found")
    return Response(content=data, media_type="application/octet-stream")
