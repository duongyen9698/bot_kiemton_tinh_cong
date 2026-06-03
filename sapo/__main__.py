"""Chạy: uv run python -m sapo [--headed] [--timeout MS]"""

from __future__ import annotations

import argparse

from sapo.pipeline import run_reconciliation_today


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Hiện cửa sổ trình duyệt khi đăng nhập (debug)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120_000,
        metavar="MS",
        help="Timeout Playwright (ms), mặc định 120000",
    )
    args = parser.parse_args()
    path = run_reconciliation_today(headed=args.headed, timeout_ms=args.timeout)
    print(f"OK: {path}")


if __name__ == "__main__":
    main()
