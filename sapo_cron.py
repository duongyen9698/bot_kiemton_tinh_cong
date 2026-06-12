"""
Cron: chạy đối soát Sapo và gửi CSV lên Telegram (cùng kiểu với khối ``if __name__ == "__main__"`` trong kiemton.py).
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from time import sleep

import requests
from dotenv import dotenv_values, load_dotenv
from telegram import Bot

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
load_dotenv(ROOT / ".env")

env = dotenv_values(ROOT / ".env")
TOKEN = env.get("TOKEN")
CHAT_ID = env.get("CHAT_ID")

LOG_FILE = ROOT / "sapo_cron.log"


def write_log(msg: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        print(msg, file=f)


def send_message(msg: str) -> None:
    if not TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}"
    requests.get(url, timeout=30)


async def send_csv_telegram(csv_path: Path) -> None:
    bot = Bot(token=TOKEN)
    with csv_path.open("rb") as f:
        await bot.send_document(
            caption=f"Đối soát Sapo (cron): {datetime.now().strftime('%d-%m-%Y')}",
            chat_id=CHAT_ID,
            document=f,
        )


def _cleanup_work_files(csv_path: Path) -> None:
    work = csv_path.parent
    for name in (
        "inventory_reconciliation_today.csv",
        "orders_today_limit_5000.json",
        "products_all_pages_limit_250.json",
    ):
        p = work / name
        if p.is_file():
            p.unlink()


if __name__ == "__main__":
    from sapo.pipeline import run_reconciliation_today

    error = "None"
    for attempt in range(5):
        try:
            csv_path = run_reconciliation_today()
            asyncio.run(send_csv_telegram(csv_path))
            _cleanup_work_files(csv_path)
            sys.exit(0)
        except Exception as e:
            write_log(f"Error attempt {attempt + 1}: {e}")
            error = str(e)
        sleep(60)

    send_message(msg=f"Sapo cron: thất bại sau 5 lần.\n{error}")
    sys.exit(1)
