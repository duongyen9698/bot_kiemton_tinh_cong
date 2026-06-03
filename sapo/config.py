from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from sapo.exc import SapoConfigError

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent


@dataclass(frozen=True)
class SapoSettings:
    admin_base_url: str
    cookie_file: Path
    work_dir: Path
    username: str
    password: str
    login_url_override: str | None

    @property
    def admin_hostname(self) -> str:
        host = urlparse(self.admin_base_url).hostname or ""
        if not host:
            raise SapoConfigError("SAPO_ADMIN_BASE_URL không có hostname hợp lệ.")
        return host

    @property
    def shop_domain_slug(self) -> str:
        """Tham số domain=... trên trang OAuth (ví dụ quay-thuoc-hai-yen-98)."""
        h = self.admin_hostname
        if h.endswith(".mysapo.net"):
            return h[: -len(".mysapo.net")]
        return h.split(".")[0]


def _strip_base(url: str) -> str:
    return url.strip().rstrip("/")


def load_settings() -> SapoSettings:
    base = _strip_base(os.environ.get("SAPO_ADMIN_BASE_URL", ""))
    if not base:
        raise SapoConfigError(
            "Thiếu SAPO_ADMIN_BASE_URL (ví dụ https://ten-cua-hang.mysapo.net)."
        )

    work_raw = os.environ.get("SAPO_WORK_DIR", "").strip()
    work_dir = Path(work_raw).expanduser() if work_raw else PROJECT_ROOT / "sapo_work"
    work_dir = work_dir.resolve()

    cookie_raw = os.environ.get("SAPO_COOKIE_FILE", "").strip()
    cookie_file = (
        Path(cookie_raw).expanduser().resolve()
        if cookie_raw
        else (work_dir / "sapo_cookies.txt")
    )

    user = os.environ.get("SAPO_USERNAME", "").strip()
    pwd = os.environ.get("SAPO_PASSWORD", "").strip()
    login_url = os.environ.get("SAPO_LOGIN_URL", "").strip() or None

    if not user or not pwd:
        raise SapoConfigError("Thiếu SAPO_USERNAME hoặc SAPO_PASSWORD trong .env.")

    return SapoSettings(
        admin_base_url=base,
        cookie_file=cookie_file,
        work_dir=work_dir,
        username=user,
        password=pwd,
        login_url_override=login_url,
    )
