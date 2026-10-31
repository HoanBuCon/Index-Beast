"""Serve only validated, content-addressed local raster images; never proxy a remote URL."""

from fastapi import APIRouter, Request, Response

from app.api.errors import ErrorBody
from core.errors import NotFoundError

router = APIRouter(tags=["images"])


@router.get(
    "/images/{image_id}",
    response_class=Response,
    responses={
        200: {
            "content": {
                mime: {"schema": {"type": "string", "format": "binary"}}
                for mime in ("image/png", "image/jpeg", "image/webp", "image/gif")
            }
        },
        304: {"description": "Unchanged verified image"},
        404: {"model": ErrorBody, "description": "Image unavailable"},
    },
    summary="Ảnh raster local đã kiểm tra hash/MIME, không nhận đường dẫn file",
)
def image(image_id: str, request: Request) -> Response:
    # Sync endpoint runs file/Pillow work in FastAPI's worker pool, never on the event loop.
    blob, _reason = request.app.state.image_catalog.read_blob(image_id)
    if blob is None:
        raise NotFoundError("Không tìm thấy ảnh hợp lệ.")
    headers = {
        "Cache-Control": "public, max-age=3600",
        "ETag": f'"{image_id}"',
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'inline; filename="{image_id}{blob.extension}"',
    }
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    return Response(content=blob.data, media_type=blob.mime, headers=headers)
