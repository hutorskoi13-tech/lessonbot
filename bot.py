import os
from datetime import date, datetime
from typing import Optional, List, Dict, Any

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler

import gspread
from google.oauth2.service_account import Credentials

# ---------- CONFIG ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
if not GOOGLE_CREDENTIALS_JSON:
    GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
else:
    GOOGLE_CREDENTIALS_FILE = "service_account.tmp.json"
    with open(GOOGLE_CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        f.write(GOOGLE_CREDENTIALS_JSON)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
sh = gc.open_by_key(GOOGLE_SHEET_ID)
try:
    ws = sh.worksheet("Plans")
except gspread.WorksheetNotFound:
    ws = sh.add_worksheet(title="Plans", rows=1000, cols=10)
    ws.append_row(["timestamp", "date", "class", "title", "note", "links"])

# ---------- HELPERS ----------
ASK_DATE, ASK_CLASS, ASK_TITLE, ASK_NOTE = range(4)

def normalize_date(s: str) -> Optional[str]:
    s = s.strip()
    if s.lower() in ("сегодня", "today"):
        return date.today().isoformat()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None

def fetch_rows(date_str: Optional[str], cls: Optional[str]) -> List[Dict[str, Any]]:
    records = ws.get_all_records()
    out = []
    for r in records:
        if date_str and r.get("date") != date_str:
            continue
        if cls and str(r.get("class","")).strip().lower() != cls.strip().lower():
            continue
        out.append(r)
    out.sort(key=lambda x: (x.get("date",""), x.get("class",""), x.get("title","")))
    return out

def format_rows(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "Ничего не найдено."
    blocks = []
    for it in items[:30]:
        blocks.append(
            f"📅 {it.get('date')} • 🎓 {it.get('class')}\n"
            f"— {it.get('title','(без названия)')}\n"
            f"{it.get('note','')}"
        )
    return "\n\n".join(blocks)

# ---------- HANDLERS ----------
def cmd_start(update, context):
    update.message.reply_text(
        "Привет! Я бот-ежедневник уроков.\n\n"
        "Команды:\n"
        "/add — добавить план (дата, класс, заметка)\n"
        "/plan — показать планы (сегодня / по дате / по классу)\n\n"
        "Примеры:\n"
        "/plan\n"
        "/plan 2025-10-21\n"
        "/plan 8A\n"
        "/plan 2025-10-21 8A"
    )

def cmd_add(update, context):
    update.message.reply_text(
        "Введите дату (YYYY-MM-DD, DD.MM.YYYY или «сегодня»):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ASK_DATE

def add_date(update, context):
    d = normalize_date(update.message.text)
    if not d:
        update.message.reply_text("Не понял дату. Формат: YYYY-MM-DD или DD.MM.YYYY:")
        return ASK_DATE
    context.user_data["date"] = d
    update.message.reply_text("Класс/группа? (например: 8A, IB HL, IGCSE-1)")
    return ASK_CLASS

def add_class(update, context):
    context.user_data["class"] = update.message.text.strip()
    update.message.reply_text("Короткий заголовок (тема):")
    return ASK_TITLE

def add_title(update, context):
    context.user_data["title"] = update.message.text.strip()
    update.message.reply_text("Заметка/план и (по желанию) ссылки:")
    return ASK_NOTE

def add_note(update, context):
    note = update.message.text.strip()
    links = " ".join([w for w in note.split() if w.startswith("http")])
    ts = datetime.now().isoformat(timespec="seconds")
    ws.append_row([ts, context.user_data["date"], context.user_data["class"],
                   context.user_data["title"], note, links])
    update.message.reply_text("Супер, сохранил ✅")
    context.user_data.clear()
    return ConversationHandler.END

def add_cancel(update, context):
    context.user_data.clear()
    update.message.reply_text("Отменено.")
    return ConversationHandler.END

def cmd_plan(update, context):
    args = context.args
    d = None
    cls = None
    if not args:
        d = date.today().isoformat()
    elif len(args) == 1:
        maybe = normalize_date(args[0])
        if maybe: d = maybe
        else: cls = args[0]
    else:
        d = normalize_date(args[0]) or args[0]
        cls = " ".join(args[1:])
    items = fetch_rows(d, cls)
    header = "Планы:\n"
    if d: header += f"• дата: {d}\n"
    if cls: header += f"• класс: {cls}\n"
    update.message.reply_text(header + "\n" + format_rows(items))

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", cmd_add)],
        states={
            ASK_DATE: [MessageHandler(Filters.text & ~Filters.command, add_date)],
            ASK_CLASS: [MessageHandler(Filters.text & ~Filters.command, add_class)],
            ASK_TITLE: [MessageHandler(Filters.text & ~Filters.command, add_title)],
            ASK_NOTE: [MessageHandler(Filters.text & ~Filters.command, add_note)],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
    )

    dp.add_handler(CommandHandler("start", cmd_start))
    dp.add_handler(add_conv)
    dp.add_handler(CommandHandler("plan", cmd_plan))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
from flask import Flask
import threading

def run_web():
    app = Flask("")
    @app.route('/')
    def home():
        return "Bot is running"
    app.run(host='0.0.0.0', port=8080)

threading.Thread(target=run_web).start()
