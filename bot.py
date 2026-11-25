# bot.py
import asyncio
import logging
import sqlite3
import random
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from config import BOT_TOKEN, OWNER_ID

# --- تنظیمات ---
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE" # <--- توکن خود را اینجا وارد کنید
OWNER_ID = 123456789 # <--- آیدی عددی خودتان را وارد کنید

logging.basicConfig(level=logging.INFO)

# --- دیتابیس ---
DB_NAME = "fox_reporter.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        role TEXT DEFAULT 'user',
        subscription_until TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        is_blocked INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone_number TEXT UNIQUE,
        api_id INTEGER,
        api_hash TEXT,
        session_string TEXT,
        status TEXT DEFAULT 'active',
        assigned_to_admin_id INTEGER,
        last_used TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS smtp_servers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        password TEXT,
        host TEXT DEFAULT 'smtp.gmail.com',
        port INTEGER DEFAULT 587,
        is_active INTEGER DEFAULT 1
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS reports_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_type TEXT,
        target_id TEXT,
        reporter_user_id INTEGER,
        status TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    # Default Settings
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('mandatory_channel_id', '')")
    conn.commit()
    conn.close()

def add_user(user_id, username=None, role='user'):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO users (user_id, username, role) VALUES (?, ?, ?)", (user_id, username, role))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def update_role(user_id, role):
    conn = get_db()
    conn.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))
    conn.commit()
    conn.close()

def log_report(target_type, target_id, reporter_id, status):
    conn = get_db()
    conn.execute("INSERT INTO reports_log (target_type, target_id, reporter_user_id, status) VALUES (?, ?, ?, ?)",
                 (target_type, target_id, reporter_id, status))
    conn.commit()
    conn.close()

def get_reports_stats(user_id=None):
    conn = get_db()
    if user_id:
        total = conn.execute("SELECT COUNT(*) FROM reports_log WHERE reporter_user_id = ?", (user_id,)).fetchone()[0]
        success = conn.execute("SELECT COUNT(*) FROM reports_log WHERE reporter_user_id = ? AND status = 'success'", (user_id,)).fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM reports_log WHERE reporter_user_id = ? AND status = 'failed'", (user_id,)).fetchone()[0]
    else:
        total = conn.execute("SELECT COUNT(*) FROM reports_log").fetchone()[0]
        success = conn.execute("SELECT COUNT(*) FROM reports_log WHERE status = 'success'").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM reports_log WHERE status = 'failed'").fetchone()[0]
    conn.close()
    return {"total": total, "success": success, "failed": failed}

# --- State Management ---
pending_operations = {}

# --- Handlers ---
dp = Dispatcher()
bot = Bot(token=BOT_TOKEN)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        add_user(message.from_user.id, message.from_user.username)
        user = get_user(message.from_user.id)

    if user.get('is_blocked'):
        await message.answer("🚫 شما محروم شده‌اید.")
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="📢 ریپورت", callback_data="report_menu")
    kb.button(text="👤 حساب من", callback_data="my_account")
    kb.button(text="🎧 پشتیبانی", callback_data="support")
    kb.button(text="⚙️ پنل ادمین", callback_data="admin_panel") if user.get('role') in ['admin', 'owner'] else None

    welcome_text = """🦊 <b>به Fox Reporter خوش آمدید!</b>\n\nبرای شروع یکی از گزینه‌های زیر را انتخاب کنید."""
    await message.answer(welcome_text, reply_markup=kb.as_markup())

@dp.callback_query(F.data == "report_menu")
async def cb_report_menu(callback: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="📝 کانال", callback_data="rep_channel")
    kb.button(text="👥 گروه", callback_data="rep_group")
    kb.button(text="📄 پست", callback_data="rep_post")
    kb.button(text="👤 پروفایل", callback_data="rep_profile")
    kb.button(text="🔙 بازگشت", callback_data="back_home")
    await callback.message.edit_text("نوع هدف را انتخاب کنید:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("rep_"))
async def cb_select_target(callback: CallbackQuery):
    target_type = callback.data.replace("rep_", "")
    pending_operations[callback.from_user.id] = {'type': target_type, 'step': 'waiting_link'}
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت", callback_data="report_menu")
    await callback.message.edit_text(f"🔗 لینک یا آیدی {target_type} را ارسال کنید:", reply_markup=kb.as_markup())

@dp.message(F.text)
async def process_input(message: Message):
    user_id = message.from_user.id
    if user_id in pending_operations and pending_operations[user_id].get('step') == 'waiting_link':
        target_type = pending_operations[user_id]['type']
        link = message.text.strip()
        pending_operations.pop(user_id)
        await simulate_report(message, target_type, link, user_id)

async def simulate_report(message: Message, target_type: str, target_id: str, user_id: int):
    progress_msg = await message.answer(f"🔄 شروع ریپورت {target_type}...")

    # شبیه‌سازی ساده
    for i in range(1, 6):
        await asyncio.sleep(1)
        status = "success" if random.random() > 0.2 else "failed"
        log_report(target_type, target_id, user_id, status)

        percent = i * 20
        await progress_msg.edit_text(f"🔄 گزارش پیشرفت:\n✅ موفق: {i-1}\n❌ ناموفق: {5-i}\n📊 درصد: {percent}%")

    await progress_msg.edit_text(f"✅ عملیات تمام شد!")

@dp.callback_query(F.data == "my_account")
async def cb_my_account(callback: CallbackQuery):
    stats = get_reports_stats(callback.from_user.id)
    text = f"👤 <b>آمار شما:</b>\nکل: {stats['total']}\nموفق: {stats['success']}\nناموفق: {stats['failed']}"
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت", callback_data="home")
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 کاربران", callback_data="adm_users")
    kb.button(text="🔙 بازگشت", callback_data="home")
    await callback.message.edit_text("پنل مدیریت:", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "back_home")
async def cb_back_home(callback: CallbackQuery):
    await callback.message.delete()
    await cmd_start(callback.message)

async def main():
    init_db()
    print("Bot started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())