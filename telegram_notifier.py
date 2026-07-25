import os
import json
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import requests

# --- LẤY THÔNG TIN TỪ GITHUB SECRETS ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GCP_SA_JSON = os.environ.get("GCP_CREDENTIALS")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1SQrD2ps8L9mEXM8UTsqMalI090_mMT3WTLHY9lAhtBI/edit"

def get_tasks_for_today():
    # Biến chuỗi JSON từ GitHub Secret thành dictionary
    creds_dict = json.loads(GCP_SA_JSON)
    creds = Credentials.from_service_account_info(
        creds_dict, 
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(SPREADSHEET_URL)
    ws_tasks = sheet.worksheet("Tasks")
    
    records = ws_tasks.get_all_records()
    if not records:
        return []
        
    df = pd.DataFrame(records)
    today_str = datetime.today().strftime("%d/%m/%Y")
    
    today_tasks = df[(df['Ngày thực hiện'] == today_str) & (df['Trạng thái'] != "Hoàn thành")]
    return today_tasks.to_dict('records')

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    requests.post(url, json=payload)

def main():
    tasks = get_tasks_for_today()
    if not tasks:
        print("Không có task hôm nay.")
        return

    msg = "🚨 <b>BÁO CÁO TASK HÔM NAY</b> 🚨\n\n"
    for idx, t in enumerate(tasks, 1):
        ten = t.get('Tên người nhận', 'Không rõ')
        task_name = t.get('Tên Task', 'Không rõ')
        msg += f"<b>{idx}. {ten}</b>: {task_name}\n"
    
    msg += "\n🔥 <i>Vào app check ngay kẻo lỡ nha sếp!</i>"
    send_telegram_message(msg)
    print("Đã bắn thông báo!")

if __name__ == "__main__":
    main()
