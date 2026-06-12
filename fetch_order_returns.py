"""CLI cũ — gọi module sapo.fetch_order_returns."""

from __future__ import annotations

import json

from dotenv import load_dotenv

from sapo.config import PROJECT_ROOT, load_settings
from sapo.fetch_order_returns import fetch_order_returns_today_json
from sapo.session import with_sapo_auth


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    settings = load_settings()
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.work_dir / "order_returns_today_limit_1000.json"

    def fetch() -> dict:
        return fetch_order_returns_today_json(settings)

    data = with_sapo_auth(settings, fetch)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved to {output_path}")
    if isinstance(data, dict):
        print("Top-level keys:", ", ".join(data.keys()))


if __name__ == "__main__":
    main()
