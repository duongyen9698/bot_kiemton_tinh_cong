from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

VN_TZ = timezone(timedelta(hours=7))
MAX_DATE_RANGE_DAYS = 366


class DateRangeError(ValueError):
    """Ngày không hợp lệ hoặc khoảng ngày vượt giới hạn."""


def parse_date_param(value: str) -> date:
    """Parse ``01/05/2026`` (ưu tiên) hoặc ``2026-05-01``."""
    text = value.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise DateRangeError(
        f"Ngày không hợp lệ: {value!r}. Dùng dd/mm/yyyy hoặc yyyy-mm-dd."
    )


def format_vn_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def validate_date_range(start: date, end: date) -> None:
    if start > end:
        raise DateRangeError(
            f"from_date ({format_vn_date(start)}) phải <= to_date ({format_vn_date(end)})."
        )
    span = (end - start).days + 1
    if span > MAX_DATE_RANGE_DAYS:
        raise DateRangeError(
            f"Khoảng ngày tối đa {MAX_DATE_RANGE_DAYS} ngày (hiện tại {span} ngày)."
        )


def build_utc_window_for_vn(start: date, end: date) -> tuple[str, str]:
    """
    Chuyển khoảng ngày VN sang UTC ISO cho Sapo API.

    start: 00:00:00.000 VN, end: 23:59:59.999 VN.
    """
    validate_date_range(start, end)
    start_vn = datetime(start.year, start.month, start.day, 0, 0, 0, tzinfo=VN_TZ)
    end_vn = datetime(end.year, end.month, end.day, 23, 59, 59, 999_000, tzinfo=VN_TZ)
    start_utc = start_vn.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_utc = end_vn.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return start_utc, end_utc


def build_today_utc_window_for_vn() -> tuple[str, str]:
    today = datetime.now(VN_TZ).date()
    return build_utc_window_for_vn(today, today)


def today_vn() -> date:
    return datetime.now(VN_TZ).date()
