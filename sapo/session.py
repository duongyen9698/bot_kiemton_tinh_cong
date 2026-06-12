from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from sapo.config import SapoSettings
from sapo.exc import SapoAuthError
from sapo.login import login_and_save_cookies

T = TypeVar("T")


def cookie_nonempty(settings: SapoSettings) -> bool:
    p = settings.cookie_file
    if not p.is_file():
        return False
    return bool(p.read_text(encoding="utf-8").strip())


def with_sapo_auth(
    settings: SapoSettings,
    fetch_fn: Callable[[], T],
    *,
    headed: bool = False,
    timeout_ms: int = 120_000,
) -> T:
    """
    Gọi ``fetch_fn``; nếu cookie trống hoặc ``SapoAuthError`` thì đăng nhập lại và thử một lần.
    """
    if not cookie_nonempty(settings):
        login_and_save_cookies(settings, headed=headed, timeout_ms=timeout_ms)

    try:
        return fetch_fn()
    except SapoAuthError:
        login_and_save_cookies(settings, headed=headed, timeout_ms=timeout_ms)
        return fetch_fn()
