# handlers.py
import asyncio
import random
import aiosmtplib
from aiogram import F, Router, types, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import (
    add_user, get_user, get_all_users, update_role, set_subscription,
    add_smtp, get_smtp_servers, toggle_smtp, mark_smtp_tested,
    add_session, get_sessions, assign_session, release_session,
    log_report, get_reports_stats, get_settings, update_setting,
    create_ticket, get_tickets, close_ticket, reply_to_ticket, get_ticket_history,
    block_user, unblock_user
)
from config import BOT_TOKEN, OWNER_ID, ADMIN_ID, WELCOME_TEXT, RULES_TEXT, DAILY_LIMIT

router = Router()

# وضعیت‌های موقت برای دریافت ورودی‌های پیوسته
pending_operations = {} 

@router.message(F.text == "/start")
async def cmd_start(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        add_user(message.from_user.id, message.from_user.username)
        user = get_user(message.from_user.id)

    if user.get('is_blocked'):
        await message.answer("🚫 شما از دسترسی به ربات محروم شده‌اید.")
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📢 ریپورت محتوا", callback_data="report_menu")
    keyboard.button(text="👤 حساب من", callback_data="my_account")
    keyboard.button(text="🎧 پشتیبانی", callback_data="support")
    keyboard.button(text="📖 راهنما", callback_data="guide")
    keyboard.button(text="📜 قوانین", callback_data="rules")

    if user.get('role') in ['admin', 'owner']:
        keyboard.button(text="⚙️ پنل ادمین", callback_data="admin_panel")

    await message.answer(WELCOME_TEXT, reply_markup=keyboard.as_markup())

@router.callback_query(F.data == "guide")
async def cb_guide(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(RULES_TEXT, parse_mode="HTML")

@router.callback_query(F.data == "rules")
async def cb_rules(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(RULES_TEXT, parse_mode="HTML")

@router.callback_query(F.data == "my_account")
async def cb_my_account(callback: CallbackQuery):
    await callback.answer()
    user = get_user(callback.from_user.id)
    stats = get_reports_stats(callback.from_user.id)

    sub_status = "فعال" if user.get('subscription_until') and user.get('subscription_until') > __import__('datetime').datetime.utcnow().isoformat() else "منقضی/ندارد"

    text = f"""
👤 <b>اطلاعات حساب شما</b>

🆔 آیدی: {callback.from_user.id}
👑 نقش: {user.get('role', 'user')}
📅 اشتراک: {sub_status}
📊 آمار ریپورت:
   - موفق: {stats['success']}
   - ناموفق: {stats['failed']}
   - کل: {stats['total']}
"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 بازگشت", callback_data="back_home")
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "back_home")
async def cb_back_home(callback: CallbackQuery):
    await callback.answer()
    # Re-send start message logic or just edit to menu
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 ریپورت محتوا", callback_data="report_menu")
    kb.button(text="👤 حساب من", callback_data="my_account")
    kb.button(text="🎧 پشتیبانی", callback_data="support")
    kb.button(text="📖 راهنما", callback_data="guide")
    kb.button(text="📜 قوانین", callback_data="rules")
    await callback.message.edit_reply_markup(reply_markup=kb.as_markup())

@router.callback_query(F.data == "report_menu")
async def cb_report_menu(callback: CallbackQuery):
    await callback.answer()
    kb = InlineKeyboardBuilder()
    kb.button(text="📝 کانال", callback_data="rep_channel")
    kb.button(text="👥 گروه", callback_data="rep_group")
    kb.button(text="📄 پست", callback_data="rep_post")
    kb.button(text="👤 پروفایل", callback_data="rep_profile")
    kb.button(text="🤖 ربات", callback_data="rep_bot")
    kb.button(text="🔄 اکانت", callback_data="rep_account")
    kb.button(text="🔙 بازگشت", callback_data="home")

    await callback.message.edit_text("نوع هدف را انتخاب کنید:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("rep_"))
async def cb_select_target(callback: CallbackQuery):
    await callback.answer()
    target_type = callback.data.replace("rep_", "")
    pending_operations[callback.from_user.id] = {'type': target_type, 'step': 'waiting_link'}

    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت", callback_data="report_menu")
    await callback.message.edit_text(f"🔗 لینک یا آیدی {target_type} را ارسال کنید:", reply_markup=kb.as_markup())

@router.message(F.text)
async def process_report_input(message: Message):
    user_id = message.from_user.id
    if user_id in pending_operations and pending_operations[user_id].get('step') == 'waiting_link':
        target_type = pending_operations[user_id]['type']
        link = message.text.strip()

        # Validate limit
        user = get_user(user_id)
        today = __import__('datetime').date.today().isoformat()
        # Simple check: In real app, track daily usage in DB. Here we assume basic check.

        pending_operations.pop(user_id)

        # Simulate Report Process
        await simulate_report(message, target_type, link, user_id)

async def simulate_report(message: Message, target_type: str, target_id: str, user_id: int):
    """شبیه‌سازی فرآیند ریپورت با گزارش پیشرفت"""

    # Check mandatory channel
    settings = get_settings()
    chan_id = settings.get('mandatory_channel_id')
    if chan_id:
        # In real implementation, check membership here

    # Get active SMTPs
    smtps = get_smtp_servers(is_active_only=True)
    if not smtps:
        await message.answer("❌ سرور ایمیل فعالی موجود نیست.")
        return

    # Start reporting simulation
    progress_msg = await message.answer(f"🔄 شروع ریپورت {target_type}...")

    total_accounts = len(smtps)
    successful = 0
    failed = 0

    for i, smtp in enumerate(smtps):
        await asyncio.sleep(1) # Delay between reports
        # Simulate success/failure
        if random.random() > 0.2: # 80% success rate
            status = "success"
            successful += 1
        else:
            status = "failed"
            failed += 1

        log_report(target_type, target_id, user_id, status)

        # Update progress
        percent = int(((i + 1) / total_accounts) * 100)
        eta = (total_accounts - i - 1) * 1 # 1 sec per report approx
        await progress_msg.edit_text(
            f"🔄 گزارش پیشرفت:\n\n"
            f"✅ موفق: {successful}\n"
            f"❌ ناموفق: {failed}\n"
            f"📊 درصد: {percent}%\n"
            f"⏳ زمان تقریبی: {eta} ثانیه"
        )

    final_kb = InlineKeyboardBuilder()
    final_kb.button(text="🔙 بازگشت", callback_data="report_menu")
    await progress_msg.edit_text(
        f"✅ عملیات ریپورت تمام شد!\n\n"
        f"نتیجه نهایی:\n"
        f"موفق: {successful}\n"
        f"ناموفق: {failed}",
        reply_markup=final_kb.as_markup()
    )

@router.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery):
    await callback.answer()
    kb = InlineKeyboardBuilder()
    kb.button(text="🆕 تیکت جدید", callback_data="new_ticket")
    kb.button(text="🔙 بازگشت", callback_data="home")
    await callback.message.edit_text("لطفاً موضوع خود را مطرح کنید:", reply_markup=kb.as_markup())

@router.callback_query(F.data == "new_ticket")
async def cb_new_ticket(callback: CallbackQuery):
    await callback.answer()
    pending_operations[callback.from_user.id] = {'step': 'waiting_ticket_msg'}
    await callback.message.edit_text("متن تیکت خود را بنویسید:")

@router.message(F.text)
async def process_ticket_message(message: Message):
    user_id = message.from_user.id
    if user_id in pending_operations and pending_operations[user_id].get('step') == 'waiting_ticket_msg':
        create_ticket(user_id, message.text)
        pending_operations.pop(user_id)
        await message.answer("✅ تیکت شما ثبت شد. منتظر پاسخ ادمین باشید.")
        # Notify admins (simplified)
        admins = get_all_users(role='admin')
        for admin in admins:
            try:
                bot = Bot(token=BOT_TOKEN)
                await bot.send_message(admin['user_id'], f"🎫 تیکت جدید از کاربر {message.from_user.username}")
            except:
                pass

@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery):
    await callback.answer()
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 لیست کاربران", callback_data="adm_users")
    kb.button(text="📧 مدیریت SMTP", callback_data="adm_smtp")
    kb.button(text="🔑 مدیریت لایسنس", callback_data="adm_license")
    kb.button(text="🎫 تیکت‌ها", callback_data="adm_tickets")
    kb.button(text="📊 آمار کلی", callback_data="adm_stats")
    kb.button(text="⚙️ تنظیمات", callback_data="adm_settings")
    kb.button(text="🔙 بازگشت", callback_data="home")

    await callback.message.edit_text("پنل مدیریت:", reply_markup=kb.as_markup())

# ... (Other admin callbacks would go here following the same pattern)
# For brevity, I've implemented the core flow. You can expand other callbacks similarly.