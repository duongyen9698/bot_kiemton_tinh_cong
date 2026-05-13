import asyncio
import base64
import json
import logging
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import sleep

import pandas as pd
import pytz
import requests
from dotenv import dotenv_values, load_dotenv
from icecream import ic
from telegram import Bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

JWT = ""
EXCEL_FOLDER = "excel"
RESULT_FILE = "result.csv"
LOG_FILE = "log.txt"
TOKEN_WARNING_STATE_FILE = "token_warning.json"
Path(EXCEL_FOLDER).mkdir(parents=True, exist_ok=True)

load_dotenv()  # take environment variables from .env

env = dotenv_values(".env")
TOKEN = env.get("TOKEN")
CHAT_ID = env.get("CHAT_ID")

PROXY = {
}


def send_message(msg):
    url = (
        f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}"
    )

    response = requests.get(url)


async def send_file(filepath):
    bot = Bot(token=TOKEN)
    file = open(filepath, "rb")
    await bot.send_document(
        caption=f"Tổng kết bán hàng cuối ngày: {datetime.now().strftime('%d-%m-%Y')}",
        chat_id=CHAT_ID,
        document=file,
    )


def read_token():
    with open("token.txt", "r") as f:
        return f.read().strip()


def write_token(token):
    with open("token.txt", "w") as f:
        f.write(token)


def write_log(msg):
    with open(LOG_FILE, "a") as f:
        print(msg, file=f)


def _base64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def parse_jwt_exp(token_str: str) -> datetime | None:
    """
    Best-effort decode JWT payload and return exp as UTC datetime.
    Signature is NOT verified (we only need expiry info).
    """
    try:
        parts = (token_str or "").strip().split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        payload = json.loads(_base64url_decode(payload_b64).decode("utf-8"))
        exp = payload.get("exp")
        if exp is None:
            return None
        exp_int = int(exp)
        return datetime.fromtimestamp(exp_int, tz=timezone.utc)
    except Exception:
        return None


def _load_token_warning_state() -> dict:
    try:
        return json.loads(Path(TOKEN_WARNING_STATE_FILE).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_token_warning_state(state: dict) -> None:
    Path(TOKEN_WARNING_STATE_FILE).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _today_str_hcm(now_utc: datetime | None = None) -> str:
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    return now_utc.astimezone(tz).strftime("%Y-%m-%d")


def should_send_token_warning(today_str: str) -> bool:
    state = _load_token_warning_state()
    return state.get("last_warn_date") != today_str


def mark_token_warning_sent(today_str: str) -> None:
    state = _load_token_warning_state()
    state["last_warn_date"] = today_str
    _save_token_warning_state(state)


def send_token_expiry_warning_if_needed() -> None:
    """
    Send a separate Telegram message when token expiry is within 3 days (or already expired),
    deduped to at most once per day (Asia/Ho_Chi_Minh).
    """
    try:
        token_str = read_token()
        exp_dt_utc = parse_jwt_exp(token_str)
        if not exp_dt_utc:
            return

        now_utc = datetime.now(timezone.utc)
        seconds_left = (exp_dt_utc - now_utc).total_seconds()

        threshold_seconds = timedelta(days=3).total_seconds()
        if seconds_left > threshold_seconds:
            return

        today_str = _today_str_hcm(now_utc=now_utc)
        if not should_send_token_warning(today_str=today_str):
            return

        tz = pytz.timezone("Asia/Ho_Chi_Minh")
        exp_dt_hcm = exp_dt_utc.astimezone(tz)

        if seconds_left >= 0:
            days_left = seconds_left / 86400
            msg = (
                "⚠️ Cảnh báo: token KiotViet sắp hết hạn.\n"
                f"- Hết hạn lúc: {exp_dt_hcm.strftime('%d-%m-%Y %H:%M:%S')} (Asia/Ho_Chi_Minh)\n"
                f"- Còn khoảng: {days_left:.2f} ngày\n"
                "Vui lòng cập nhật token sớm."
            )
        else:
            msg = (
                "⛔ Token KiotViet đã hết hạn.\n"
                f"- Hết hạn lúc: {exp_dt_hcm.strftime('%d-%m-%Y %H:%M:%S')} (Asia/Ho_Chi_Minh)\n"
                "Vui lòng cập nhật token."
            )

        send_message(msg=msg)
        mark_token_warning_sent(today_str=today_str)
    except Exception:
        # Never break the job because of warning logic
        return


class Kiotviet:
    def get_headers(self):
        headers = {
            "authority": "api-man1.kiotviet.vn",
            "accept": "application/json, text/plain, */*",
            "accept-language": "vi-VN,vi;q=0.9,en;q=0.8,ru;q=0.7",
            "authorization": f"Bearer {read_token()}",
            "branchid": "225357",
            "content-type": "application/json;charset=utf-8",
            "fingerprintkey": "7ef50ff5ee7f281739b180cfe18698c3_Chrome_Desktop_Máy tính Mac OS",
            "isusekvclient": "1",
            "origin": "https://nhathuochaiyenbg.kiotviet.vn",
            "referer": "https://nhathuochaiyenbg.kiotviet.vn/",
            "retailer": "nhathuochaiyenbg",
            "sec-ch-ua": '"Chromium";v="116", "Not)A;Brand";v="24", "Google Chrome";v="116"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
            "x-group-id": "18",
            "x-retailer-code": "nhathuochaiyenbg",
        }
        return headers

    def get_file_name(self, file_prefix: str):
        now = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))
        # 07092023-194045
        now_str = now.strftime("%d%m%Y-%H%M%S")
        self.filename = f"{file_prefix}{now_str}-{random.randint(100, 999)}"
        logging.info(f"File name: {self.filename}")
        write_log(f"File name: {self.filename}")

    def export(self, json_data: dict):
        response = requests.post(
            "https://api-man1.kiotviet.vn/api/importexportfiles/exportfile",
            headers=self.get_headers(),
            json=json_data,
        )

        self.Revision = response.json().get("Data", {}).get("Revision", "")
        logging.info(f"Revision: {self.Revision}")
        write_log(f"Revision: {self.Revision}")

    def importexportfiles(self):
        params = {
            "Revision": self.Revision,
            "ModifiedDate": datetime.now(pytz.timezone("UTC")).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
        }

        for i in range(20):
            logging.info(f"Trying to get file path => {i} time(s)")
            write_log(f"Trying to get file path => {i} time(s)")
            response = requests.get(
                "https://api-man1.kiotviet.vn/api/importexportfiles",
                params=params,
                headers=self.get_headers(),
            )
            ic(response.json())

            # logging.info(json.dumps(response.json(), indent=4))

            self.FilePath = response.json().get("Data", [])
            if self.FilePath:
                self.FilePath = self.FilePath[0].get("FilePath", "")

            if self.FilePath:
                logging.info(f"Got FilePath: {self.FilePath}")
                write_log(f"Got FilePath: {self.FilePath}")
                break
            sleep(1)

    def download_file(self):
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "vi-VN,vi;q=0.9,en;q=0.8,ru;q=0.7",
            # 'cookie': 'gkvas-uuid=afc36b61-65be-4b6b-92a9-0f399260b6c5; gkvas-uuid-d=1706177550722; _fw_crm_v=22d93d20-5d76-4078-aaeb-98b84922b705; ktarget_retailer_id=1181435',
            "priority": "u=0, i",
            "sec-ch-ua": '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        }
        response = requests.get(
            self.FilePath, headers=headers, proxies=PROXY, timeout=10
        )

        self.saved_file = os.path.join(EXCEL_FOLDER, self.FilePath.split("/")[-1])
        with open(self.saved_file, "wb") as f:
            f.write(response.content)

    def run(self):
        # Get bills
        self.get_file_name(file_prefix="DanhSachChiTietHoaDon_KV")
        self.export(
            json_data={
                "Type": "InvoiceWithDetail",
                "FileName": self.filename,
                "Filters": '{"__type":"KiotViet.Web.Api.InvoiceList, KiotViet.Web.Api","Includes":["BranchName","Branch","DeliveryPackages","Customer","Payments","SoldBy","User","InvoiceOrderSurcharges","Order","SaleChannel","Returns","InvoiceMedicine","PriceBook"],"ForSale":false,"TotalValueOnly":false,"ForSummaryRow":false,"ForReturn":false,"ForExportDetail":false,"ExpectedDeliveryFilterType":"alltime","UsingStoreProcedure":false,"FiltersForOrm":"{\\"BranchIds\\":[225357],\\"PriceBookIds\\":[],\\"FromDate\\":null,\\"ToDate\\":null,\\"TimeRange\\":\\"today\\",\\"InvoiceStatus\\":[\\"3\\",\\"1\\"],\\"UsingCod\\":[],\\"TableIds\\":[],\\"SalechannelIds\\":[],\\"StartDeliveryDate\\":null,\\"EndDeliveryDate\\":null,\\"UsingPrescription\\":2}","IsCheckTransaction":false,"ForReturnFilter":false,"ForPromotionHistory":false,"UsingTotalApi":true,"SkipUseOrmLite":false,"SkipZipExported":false,"FromSale":false,"$top":15,"$filter":"(PurchaseDate eq \'today\' and (Status eq 3 or Status eq 1))","Ids":null,"InvoiceFilterForExport":{"BranchId":[225357]}}',
                "Columns": "[]",
                "Revision": None,
                "Page": "#/Invoices",
            }
        )
        self.importexportfiles()
        self.download_file()

        self.bill_df = pd.read_excel(self.saved_file)
        os.remove(self.saved_file)

        # Get products
        print(f"Getting products...")
        self.get_file_name(file_prefix="DanhSachSanPham_KV")
        self.export(
            json_data={
                "Type": "Product",
                "FileName": self.filename,
                "Filters": '{"CategoryId":0,"AttributeFilter":"[]","BranchId":-1,"ProductTypes":"","IsImei":2,"IsFormulas":2,"IsActive":true,"AllowSale":null,"IsBatchExpireControl":2,"ShelvesIds":"","TrademarkIds":"","StockoutDate":"alltime","supplierIds":"","isNewFilter":true}',
                "Revision": None,
                "Page": "#/Products",
            }
        )
        self.importexportfiles()
        self.download_file()
        self.product_df = pd.read_excel(self.saved_file)
        os.remove(self.saved_file)

        # Analyze
        self.analyze()

    def analyze(self):
        products = {}
        for row_index in self.product_df.index:
            product = self.product_df.iloc[row_index]

            code = product["Mã hàng"]
            in_storage = product["Tồn kho"]

            products[code] = in_storage

        df = pd.DataFrame(
            {
                "Mã hàng": [],
                "Tên hàng": [],
                "ĐVT": [],
                "Tồn kho": [],
            }
        )

        for row_index in self.bill_df.index:
            bill = self.bill_df.iloc[row_index]

            code = bill["Mã hàng"]
            name = bill["Tên hàng"]
            unit_name = bill["ĐVT"]

            df.loc[len(df.index)] = [code, name, unit_name, products.get(code, "-")]

        df.to_csv(RESULT_FILE)


if __name__ == "__main__":
    send_token_expiry_warning_if_needed()
    error = "None"
    for _ in range(5):
        try:
            kiotviet = Kiotviet()
            kiotviet.run()

            asyncio.run(send_file(RESULT_FILE))

            sys.exit(0)

        except Exception as e:
            write_log(f"Error: {e}")
            error = f"{e}"

        sleep(60)

    send_message(msg=f"Failed after 5 times.\n{error}")
