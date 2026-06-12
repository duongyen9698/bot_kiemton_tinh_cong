from __future__ import annotations

import asyncio
import os
from functools import lru_cache
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query

from sapo.config import PROJECT_ROOT, SapoSettings, load_settings
from sapo.dates import DateRangeError, parse_date_param
from sapo.exc import SapoAuthError, SapoConfigError
from sapo.fetch_order_returns import fetch_order_returns_json
from sapo.fetch_orders import fetch_orders_json
from sapo.fetch_products import fetch_all_products
from sapo.session import with_sapo_auth

load_dotenv(PROJECT_ROOT / ".env")

app = FastAPI(
    title="Sapo Data API",
    description="Lấy hàng hóa, hóa đơn và trả hàng từ Sapo Admin.",
    version="1.0.0",
)


@lru_cache
def get_settings() -> SapoSettings:
    try:
        return load_settings()
    except SapoConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


def verify_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    expected = os.environ.get("SAPO_API_KEY", "").strip()
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key.")


def parse_range_params(
    from_date: Annotated[str, Query(description="dd/mm/yyyy hoặc yyyy-mm-dd")],
    to_date: Annotated[str, Query(description="dd/mm/yyyy hoặc yyyy-mm-dd")],
) -> tuple:
    try:
        start = parse_date_param(from_date)
        end = parse_date_param(to_date)
        return start, end
    except DateRangeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


def _run_fetch(settings: SapoSettings, fetch_fn):
    try:
        return with_sapo_auth(settings, fetch_fn)
    except SapoConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except SapoAuthError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Không xác thực được Sapo sau khi đăng nhập lại: {e}",
        ) from e
    except DateRangeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Lỗi gọi Sapo: {e}") from e


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/products", dependencies=[Depends(verify_api_key)])
async def get_products(
    settings: Annotated[SapoSettings, Depends(get_settings)],
) -> dict:
    def fetch() -> dict:
        return fetch_all_products(settings)

    return await asyncio.to_thread(_run_fetch, settings, fetch)


@app.get("/api/v1/orders", dependencies=[Depends(verify_api_key)])
async def get_orders(
    settings: Annotated[SapoSettings, Depends(get_settings)],
    date_range: Annotated[tuple, Depends(parse_range_params)],
) -> dict:
    start_date, end_date = date_range

    def fetch() -> dict:
        return fetch_orders_json(
            settings, start_date=start_date, end_date=end_date
        )

    return await asyncio.to_thread(_run_fetch, settings, fetch)


@app.get("/api/v1/order-returns", dependencies=[Depends(verify_api_key)])
async def get_order_returns(
    settings: Annotated[SapoSettings, Depends(get_settings)],
    date_range: Annotated[tuple, Depends(parse_range_params)],
) -> dict:
    start_date, end_date = date_range

    def fetch() -> dict:
        return fetch_order_returns_json(
            settings, start_date=start_date, end_date=end_date
        )

    return await asyncio.to_thread(_run_fetch, settings, fetch)
