import asyncio
import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from time import sleep

from dotenv import dotenv_values, load_dotenv
from telegram import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageEntity,
    Update,
)
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from kiemton import RESULT_FILE, Kiotviet, write_token
from sapo.exc import SapoConfigError
from sapo.pipeline import run_reconciliation_today

DB_FILE = "db.json"

# List of allowed users (IDs or usernames)
ALLOWED_USERS = ["1655527971", "Jena882".lower()]
ALLOWED_KIEMTON_COMMAND_USERS = ["1655527971", "Jena882", "5666233114", "8499875913".lower()]


def is_user_allowed(user: Update) -> bool:
    """Check if the user is allowed to use the bot."""
    if (
        str(user.effective_user.username).lower() in ALLOWED_USERS
        or str(user.effective_user.id).strip("@") in ALLOWED_USERS
    ):
        return True
    return False

def is_kiemton_command_user(user: Update) -> bool:
    if (
        str(user.effective_user.username).lower() in ALLOWED_KIEMTON_COMMAND_USERS
        or str(user.effective_user.id).strip("@") in ALLOWED_KIEMTON_COMMAND_USERS
    ):
        return True
    return False

def restricted_kiemton_command(func):
    """Decorator to restrict access to certain commands."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if is_kiemton_command_user(update):
            await func(update, context, *args, **kwargs)
        else:
            await update.message.reply_text("You are not authorized to use this command.")
    return wrapper

def restricted(func):
    """Decorator to restrict access to certain commands."""

    async def wrapper(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
    ):
        if is_user_allowed(update):
            await func(update, context, *args, **kwargs)
        else:
            await update.message.reply_text("You are not authorized to use this bot.")

    return wrapper


def add_this_year() -> str:
    now = datetime.now()
    return "/" + str(now.year)


def get_db() -> dict:
    try:
        return json.loads(open(DB_FILE, "r").read())
    except:
        return {}


def write_db(db_dict: dict) -> None:
    with open(DB_FILE, "w") as f:
        f.write(json.dumps(db_dict, indent=4, ensure_ascii=False))


def get_off_hours_str(off_hours) -> str:
    return f"Số giờ nghỉ: {off_hours} giờ." if off_hours else ""


@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Hello {update.message.from_user.first_name}",
        parse_mode="HTML",
    )


@restricted
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(text="Pong!", parse_mode="HTML")


# @restricted
async def getchat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id

    await update.message.reply_text(text=f"Chat ID: {chat_id}\nUser ID: {user_id}")


@restricted
async def batdau(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text(
            text="""Nhập ngày bắt đầu tính công
Ví dụ:  /batdau 15/4
        /batdau 15/4 12""",
            parse_mode="HTML",
        )
        return

    try:
        if len(context.args) >= 2 and context.args[1] == "12":
            hour_str = " 12:00:00"
        else:
            hour_str = " 00:00:00"
        input_date_str = context.args[0] + add_this_year() + hour_str
        input_date = datetime.strptime(input_date_str, "%d/%m/%Y %H:%M:%S")

        db_dict = get_db()
        db_dict["batdau"] = input_date_str
        db_dict["nghi"] = {}

        write_db(db_dict)
        await update.message.reply_text(
            text=f"Đã cài đặt ngày bắt đầu là: {input_date_str}"
        )
    except:
        await update.message.reply_text(
            text="Có lỗi xảy ra, liên hệ với Chồng boé nhé bà chủ"
        )


@restricted
async def nghi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    def format_hours() -> int:
        if len(context.args) < 2:
            return 24
        off_hours = 0
        for ch in context.args[1]:
            if ch.isdigit():
                off_hours = off_hours * 10 + int(ch)

        return off_hours

    if len(context.args) < 1:
        await update.message.reply_text(
            text="""Nhập thêm ngày nghỉ
Ví dụ:  /nghi 25/4
        /nghi 2/5 12
        /nghi 30/4 0""",
            parse_mode="HTML",
        )
        return

    try:
        input_date_str = context.args[0] + add_this_year()
        off_hours = format_hours()
        input_date = datetime.strptime(input_date_str, "%d/%m/%Y")
        db_dict = get_db()

        db_dict_nghi = db_dict.get("nghi", {})
        db_dict_nghi[input_date_str] = off_hours
        db_dict["nghi"] = db_dict_nghi

        write_db(db_dict)

        await update.message.reply_text(
            text=f"Đã thêm ngày nghỉ{' LỄ' if off_hours == '0' else ''} {input_date_str}."
            + get_off_hours_str(off_hours=off_hours)
        )
    except Exception as e:
        print(e)
        await update.message.reply_text(
            text="Có lỗi xảy ra, liên hệ với Chồng boé nhé vợ iu"
        )


@restricted
async def xoa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text(
            text="""Nhập ngày để xoá khỏi ngày nghỉ
Ví dụ: /xoa 25/4""",
            parse_mode="HTML",
        )
        return

    try:
        input_date_str = context.args[0] + add_this_year()
        input_date = datetime.strptime(input_date_str, "%d/%m/%Y")
        db_dict = get_db()

        db_dict_nghi = db_dict.get("nghi", {})
        db_dict_nghi.pop(input_date_str, None)
        db_dict["nghi"] = db_dict_nghi

        write_db(db_dict)

        await update.message.reply_text(text=f"Đã xoá ngày nghỉ: {input_date_str}")
    except:
        await update.message.reply_text(
            text="Có lỗi xảy ra, liên hệ với Chồng boé nhé vợ iu"
        )


@restricted
async def tinh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db_dict = get_db()
        sorted_days_off_dict = sorted(
            db_dict.get("nghi", {}).items(),
            key=lambda x: (int(x[1]), datetime.strptime(x[0], "%d/%m/%Y")),
        )
        start_day_str = db_dict.get("batdau", "")
        start_day = datetime.strptime(start_day_str, "%d/%m/%Y %H:%M:%S")
        msg = f"Ngày bắt đầu tính công: {start_day_str}"
        if sorted_days_off_dict:
            msg += f"\nDanh sách ngày nghỉ:"
        for day in sorted_days_off_dict:
            day_off, off_hours = day
            msg += (
                f"\nNghỉ {'LỄ ' if off_hours == '0' else ''}ngày: {day_off}."
                + get_off_hours_str(off_hours=off_hours)
            )

        # print(sorted_days_off_dict)
        sum_hours_off = sum(int(day[-1]) for day in sorted_days_off_dict)
        # print(sum_hours_off)
        _28days = start_day + timedelta(days=28) + timedelta(hours=sum_hours_off)

        msg += f"\n\nNgày đủ 28 công: {_28days.strftime('%d/%m/%Y %H:%M:%S')}"
        await update.message.reply_text(text=msg)

    except Exception as e:
        print(e)
        await update.message.reply_text(
            text="Có lỗi xảy ra, liên hệ với Chồng boé nhé vợ iu"
        )


@restricted
async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_dict = get_db()
    await update.message.reply_text(text=json.dumps(db_dict))


@restricted
async def update_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = "".join(context.args)
    if token:
        write_token(token=token)
        await update.message.reply_text(text="Done!")
    else:
        await update.message.reply_text(text="Please input token")


# @restricted
@restricted_kiemton_command
async def sapo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        csv_path = await asyncio.to_thread(run_reconciliation_today)
        with open(csv_path, "rb") as file:
            await update.message.reply_document(
                caption=f"Đối soát Sapo trong ngày: {datetime.now().strftime('%d-%m-%Y')}",
                document=file,
            )
        work = csv_path.parent
        for name in (
            "inventory_reconciliation_today.csv",
            "orders_today_limit_5000.json",
            "products_all_pages_limit_250.json",
        ):
            p = work / name
            if p.is_file():
                os.remove(p)
    except SapoConfigError as e:
        await update.message.reply_text(f"Cấu hình Sapo: {e}")
    except Exception as e:
        await update.message.reply_text(f"Lỗi đối soát Sapo\n{e}")


@restricted_kiemton_command
async def kiemton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        kiotviet = Kiotviet()
        kiotviet.run()

        file = open(RESULT_FILE, "rb")

        await update.message.reply_document(
            caption=f"Tổng kết bán hàng cuối ngày: {datetime.now().strftime('%d-%m-%Y')}",
            document=file,
        )
        os.remove(RESULT_FILE)

    except Exception as e:
        await update.message.reply_text(f"Error\n{e}")


strategyPatterns = {
    "ping": ping,
    "start": start,
    "getchat": getchat,
    "batdau": batdau,
    "nghi": nghi,
    "xoa": xoa,
    "tinh": tinh,
    "debug": debug,
    "sapo": sapo,
    "kiemton": kiemton,
    "token": update_token,
}

handlers = []

for key, value in strategyPatterns.items():
    handlers.append(CommandHandler(key, value))
