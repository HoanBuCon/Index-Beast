"""Hằng số dùng chung của hai service ảnh: nơi lưu cache ảnh web và các định dạng raster được chấp nhận.

Tách riêng để `images` (catalog/đọc blob) và `answer_media` (tải/chọn ảnh) không import vòng quanh nhau.
"""

from core.config import REPO_ROOT

CACHE = REPO_ROOT / "backend" / ".cache" / "web-images"
FORMATS = {
    "PNG": (".png", "image/png"),
    "JPEG": (".jpg", "image/jpeg"),
    "WEBP": (".webp", "image/webp"),
    "GIF": (".gif", "image/gif"),
}
