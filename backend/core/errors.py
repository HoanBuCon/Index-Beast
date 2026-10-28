"""Exception nghiệp vụ dùng chung. API map sang JSON {code, message, request_id} ở một chỗ (app/api/errors.py).

Thêm loại lỗi mới: kế thừa AppError, đặt `status_code` và `code` (chữ thường, ổn định — client dựa vào `code`).
`message` hiển thị được cho người dùng; không đưa chi tiết nội bộ hay secret vào đó.

Phụ trách: TV1 · [S2] Xử lý lỗi & logging chuẩn
"""


class AppError(Exception):
    status_code = 500
    code = "internal_error"
    message = "Đã xảy ra lỗi. Vui lòng thử lại sau."

    def __init__(self, message: str | None = None, *, headers: dict[str, str] | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.headers = headers or {}


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"
    message = "Yêu cầu không hợp lệ."


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Thiếu hoặc sai thông tin xác thực."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Không tìm thấy tài nguyên."


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"
    message = "Bạn đang gửi quá nhanh. Vui lòng đợi rồi thử lại."

    def __init__(self, message: str | None = None, *, retry_after: int | None = None) -> None:
        headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
        super().__init__(message, headers=headers)


class UpstreamError(AppError):
    """Dịch vụ bên ngoài (LLM, tìm web…) lỗi."""

    status_code = 502
    code = "upstream_error"
    message = "Dịch vụ phía sau gặp lỗi. Vui lòng thử lại."


class UnavailableError(AppError):
    status_code = 503
    code = "unavailable"
    message = "Dịch vụ tạm thời không khả dụng."
