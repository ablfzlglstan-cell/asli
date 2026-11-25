import asyncio
import logging
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import sqlite3
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

DB_NAME = "fox_reporter.db"
logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER NOT NULL,
                reporter_username TEXT,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()

def main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📝 ثبت گزارش"))
    builder.row(KeyboardButton(text="ℹ️ راهنما"))
    return builder.as_markup(resize_keyboard=True)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "سلام! به ربات دریافت گزارش خوش آمدی.\n"
        "برای ثبت گزارش، دکمه «📝 ثبت گزارش» را بزن.\n"
        "لطفاً فقط اطلاعاتی را ارسال کن که حق به‌اشتراک‌گذاری آن‌ها را داری.",
        reply_markup=main_keyboard()
    )

@dp.message(Command("help"))
@dp.message(F.text == "ℹ️ راهنما")
async def help_message(message: Message):
    await message.answer(
        "برای ثبت گزارش، «📝 ثبت گزارش» را بزن و توضیح روشن و مستندت را بفرست.\n"
        "از ارسال رمز عبور، کد ورود، شماره تلفن دیگران یا فایل نشست تلگرام خودداری کن."
    )

@dp.message(Command("report"))
@dp.message(F.text == "📝 ثبت گزارش")
async def ask_report(message: Message):
    await message.answer(
        "لطفاً شرح گزارش را در یک پیام بفرست. اگر لازم است، فقط پیوند عمومی محتوای موردنظر را اضافه کن.\n"
        "اطلاعات خصوصی اشخاص، رمزها و کدهای ورود را ارسال نکن."
    )

@dp.message(F.text)
async def receive_report(message: Message, bot: Bot):
    details = (message.text or "").strip()
    if len(details) < 10:
        await message.answer("لطفاً توضیح کامل‌تری بنویس (حداقل ۱۰ نویسه).")
        return
    if len(details) > 3500:
        await message.answer("متن گزارش خیلی طولانی است؛ لطفاً آن را کوتاه‌تر کن.")
        return

    username = message.from_user.username if message.from_user else None
    created_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute(
            "INSERT INTO reports (reporter_id, reporter_username, details, created_at) VALUES (?, ?, ?, ?)",
            (message.from_user.id, username, details, created_at)
        )
        report_id = cur.lastrowid
        conn.commit()

    await message.answer(f"گزارش با شماره {report_id} ثبت شد. ممنون.")

    if OWNER_ID:
        who = f"@{username}" if username else "بدون نام کاربری"
        owner_text = (
            f"📩 گزارش جدید شماره {report_id}\n"
            f"فرستنده: {who}\n"
            f"شناسه فرستنده: {message.from_user.id}\n\n"
            f"{details}"
        )
        try:
            await bot.send_message(OWNER_ID, owner_text)
        except Exception:
            logging.exception("Could not forward report to owner")

@dp.message()
async def unsupported(message: Message):
    await message.answer("فعلاً فقط گزارش متنی پذیرفته می‌شود. برای شروع /start را بزن.")

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN تنظیم نشده است.")
    if OWNER_ID <= 0:
        raise RuntimeError("OWNER_ID باید یک شناسه عددی معتبر باشد.")
    init_db()
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
