class SapoAuthError(Exception):
    """Cookie hết hạn hoặc không hợp lệ (HTTP 401/403)."""


class SapoConfigError(Exception):
    """Thiếu hoặc sai cấu hình môi trường."""
