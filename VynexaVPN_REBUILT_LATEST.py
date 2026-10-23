import random
from pathlib import Path


# ===== VYNEXA MINI APP =====


# ===== VYNEXA_REFERRAL_CHALLENGE =====
VYNEXA_REFERRAL_TEXT = """👥 زیرمجموعه‌گیری وینکسا 💙

با لینک اختصاصی خودت دوستات رو به ربات دعوت کن و جایزه بگیر! 🎁

🔥 چالش امشب: اگه ۲ نفر با لینک اختصاصی تو وارد ربات بشن و استارتش کنن، برنده‌ی یک سرویس V2Ray اقتصادی ۱۰ گیگابایتی رایگان می‌شی!

👇 لینک اختصاصی خودت رو از اینجا بگیر و برای دوستات بفرست.

💙 هر دعوت، یک قدم نزدیک‌تر به جایزه!"""

async def vynexa_webapp_data(update, context):
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        await update.effective_message.reply_text("✅ اتصال Mini App به ربات برقرار شد.")
    except Exception:
        await update.effective_message.reply_text("✅ Mini App متصل شد.")

import json, re, asyncio, random, secrets, string
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ChatJoinRequestHandler, ChatMemberHandler, ContextTypes, filters
)
from telegram.request import HTTPXRequest
try:
    from telegram import ReactionTypeEmoji
except ImportError:
    ReactionTypeEmoji = None

REACTION_EMOJIS = ['👍','❤️','😂','🔥','👏','😍','🤩','😎','💯','🎉','✨','🥰']

async def _send_reaction_fast(bot, chat_id, message_id, emoji):
    try:
        if ReactionTypeEmoji is None:
            return
        await bot.set_message_reaction(
            chat_id=chat_id,
            message_id=message_id,
            reaction=[ReactionTypeEmoji(emoji=emoji)],
            is_big=False
        )
    except Exception:
        pass


HOME = Path.home()
CONFIG_FILE = HOME / 'config.json'
ORDERS_FILE = HOME / 'orders.json'
USERS_FILE = HOME / 'users.json'
ADMIN_ID_FILE = HOME / 'admin_id.txt'
REFERRALS_FILE = HOME / 'referrals.json'
GROUP_VERIFIED_FILE = HOME / 'vynexa_group_verified.json'

SUPPORT = '@vynexavpn1'
JOIN_CHANNEL_ID = '@VynexaVPN'
JOIN_GROUP_ID = '@vynexagp'

JOIN_REQUEST_MESSAGE = """👋 درخواست عضویتت رسید 😅

فعلاً درخواستت منتظر تأیید ادمینه 👀
تا ببینیم بالاخره تأیید میشی یا نه 😂

فعلاً بیا اینجا قیمت‌ها و سرویسامونو ببین 👇
@VynexaVPN_bot"""
CHANNEL_ID = '@VynexaVPN'

WELCOME = """👋 سلام رفیق! چطور می‌تونم کمکتون کنم؟ 😊

💙 به Vynexa-VPN خوش اومدی!
اینجا می‌تونی درباره سرویس‌ها سؤال بپرسی یا با راهنمایی ربات سرویس موردنظرت رو پیدا کنی.

🛒 خرید سرویس: از منوی پایین استفاده کن
📦 سرویس‌های من: سرویس‌های فعال خودت رو ببین
🎧 پشتیبانی: برای پیگیری سفارش یا مشکلات اتصال

⚡ خوش اومدی به Vynexa-VPN!"""


def read_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            pass
    return default


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def load_config():
    return read_json(CONFIG_FILE, {})


def save_config(c):
    write_json(CONFIG_FILE, c)

def setup_ai_config():
    # پاسخ‌گویی محلی؛ بدون OpenAI و بدون API Key
    c = load_config()
    c["ai_enabled"] = False
    c["ai_mode"] = "local"
    save_config(c)
    return c


def load_orders():
    return read_json(ORDERS_FILE, {})


def save_orders(o):
    write_json(ORDERS_FILE, o)


def load_users():
    return read_json(USERS_FILE, {})


def save_users(u):
    write_json(USERS_FILE, u)



def load_referrals():
    return read_json(REFERRALS_FILE, {
        'users': {},
        'successful_customers': {},
        'pending_rewards': {}
    })


def save_referrals(data):
    write_json(REFERRALS_FILE, data)


def referral_link(uid):
    return f"https://t.me/VynexaVPN_bot?start=ref_{int(uid)}"


def register_referral_visit(uid, referrer_id):
    """ثبت معرف فقط یک‌بار؛ خودش و معرف‌های بعدی نمی‌توانند attribution را عوض کنند."""
    uid=str(uid); ref=str(referrer_id)
    if uid == ref or not ref.isdigit():
        return False
    data=load_referrals()
    users=data.setdefault('users', {})
    if uid in users and users[uid].get('referrer_id'):
        return False
    users[uid]={'referrer_id':int(ref), 'attributed_at':datetime.now().isoformat()}
    save_referrals(data)
    return True


def referral_stats(referrer_id):
    data=load_referrals(); rid=str(referrer_id)
    successful=data.setdefault('successful_customers', {}).get(rid, {})
    pending=int(data.setdefault('pending_rewards', {}).get(rid, 0) or 0)
    return successful, pending


async def record_successful_referral(context, o):
    """هر مشتری فقط یک بار، فقط بعد از خرید موفق/تحویل‌شده برای معرف حساب می‌شود."""
    if str(o.get('type','')).lower() == 'renewal':
        return
    uid=str(o.get('user_id',''))
    if not uid: return
    data=load_referrals()
    attr=data.setdefault('users', {}).get(uid)
    if not attr: return
    rid=str(attr.get('referrer_id',''))
    if not rid or rid == uid: return
    successful=data.setdefault('successful_customers', {})
    bucket=successful.setdefault(rid, {})
    if uid in bucket:
        return
    bucket[uid]={
        'order_id':str(o.get('id','')),
        'at':datetime.now().isoformat(),
    }
    count=len(bucket)
    rewards=data.setdefault('pending_rewards', {})
    old_milestones=int(rewards.get(rid,0) or 0)
    earned=count//3
    if earned > old_milestones:
        rewards[rid]=earned
        save_referrals(data)
        try:
            await context.bot.send_message(int(rid),
                '🎉 تبریک!\n\n'
                '👥 ۳ مشتری جدید با لینک زیرمجموعه‌گیری تو خرید موفق انجام دادن.\n'
                '🎁 یک جایزه ۱۰GB V2Ray یک‌ماهه اقتصادی برات آماده شد.\n\n'
                'برای دریافتش روی «🎁 دریافت جایزه» بزن.')
        except Exception as e:
            print('REFERRAL USER NOTICE ERROR:',repr(e))
        try:
            await context.bot.send_message(admin_id(),
                '🎉 تکمیل پاداش زیرمجموعه‌گیری\n\n'
                f'👤 معرف: {rid}\n'
                f'🛒 مشتری موفق: {count}\n'
                f'🎁 پاداش‌های قابل دریافت: {earned}')
        except Exception as e:
            print('REFERRAL ADMIN NOTICE ERROR:',repr(e))
    else:
        save_referrals(data)


async def referral_panel(update, context):
    uid=update.effective_user.id
    successful,pending=referral_stats(uid)
    text=(
        '🏁 چالش زیرمجموعه‌گیری وینکسا 💙\n\n'
        f'🔗 لینک اختصاصی تو:\n{referral_link(uid)}\n\n'
        '👥 چطور چالش رو کامل کنی؟\n'
        '۱. لینک اختصاصی‌ات رو برای دوستات بفرست.\n'
        '۲. دو نفر متفاوت باید از لینک تو وارد ربات بشن.\n'
        '۳. هر دو باید عضو کانال @VynexaVPN بشن.\n\n'
        '✅ بعد از تأیید عضویت هر دو نفر، گزارش تکمیل چالش برای ادمین ارسال و ذخیره می‌شه.\n'
        '📌 این چالش به‌صورت خودکار جایزه یا سرویس صادر نمی‌کنه.\n\n'
        f'🛒 مشتری موفق از خرید: {len(successful)} نفر\n'
        f'🎁 جایزه‌های خرید قابل دریافت: {pending} عدد'
    )
    buttons=[]
    if pending>0:
        buttons.append([InlineKeyboardButton('🎁 دریافت جایزه',callback_data='ref_claim')])
    buttons.append([InlineKeyboardButton('🔄 به‌روزرسانی',callback_data='ref_refresh')])
    await update.message.reply_text(text,reply_markup=InlineKeyboardMarkup(buttons))


async def referral_admin_panel(update, context):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text('⛔ فقط مدیر.')
    data=load_referrals(); successful=data.get('successful_customers',{})
    challenge_successful = data.get('challenge_successful', {})
    challenge_completions = data.get('challenge_completions', {})
    ids=set(successful.keys())
    ids.update(challenge_successful.keys())
    ids.update(challenge_completions.keys())
    for u in data.get('users',{}).values():
        rid=str(u.get('referrer_id',''))
        if rid: ids.add(rid)
    if not ids:
        return await update.message.reply_text('👥 هنوز زیرمجموعه‌ای ثبت نشده است.')
    buttons=[]
    for rid in sorted(ids,key=lambda x:len(successful.get(x,{})),reverse=True)[:50]:
        cnt=len(successful.get(rid,{})); pending=int(data.get('pending_rewards',{}).get(rid,0) or 0)
        challenge_count = len(challenge_successful.get(rid, {}))
        challenge_mark = ' — 🏁 چالش تکمیل' if rid in challenge_completions else f' — چالش {challenge_count}/2'
        buttons.append([InlineKeyboardButton(
            f'👤 {rid} — {cnt} موفق — 🎁 {pending}{challenge_mark}',
            callback_data=f'ref_admin:{rid}'
        )])

    completed = list(challenge_completions.items())
    completed.sort(key=lambda item: item[1].get('completed_at', ''), reverse=True)
    if completed:
        challenge_text = '\n\n🏁 تکمیل‌کنندگان چالش دو دعوت:\n' + '\n'.join(
            f"• آیدی معرف: {rid} | تاریخ: {record.get('completed_at', 'نامشخص')}"
            for rid, record in completed[:30]
        )
    else:
        challenge_text = '\n\n🏁 هنوز چالشی تکمیل نشده است.'
    await update.message.reply_text(
        '👥 لیست معرف‌ها:' + challenge_text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def referral_callback(update, context):
    q=update.callback_query; d=q.data; uid=q.from_user.id
    if d=='ref_refresh':
        await q.answer('آمار به‌روزرسانی شد ✅')
        successful,pending=referral_stats(uid)
        data=load_referrals()
        attributed = data.get("users", {})
        my_visits = sum(
            1 for invited in attributed.values()
            if str(invited.get("referrer_id", "")) == str(uid)
        )
        challenge_count = len(data.get("challenge_successful", {}).get(str(uid), {}))
        completed = str(uid) in data.get("challenge_completions", {})
        challenge_status = "✅ چالش تکمیل شده" if completed else f"⏳ پیشرفت چالش: {challenge_count}/2"
        return await q.message.reply_text(
            "👥 آمار زیرمجموعه‌گیری تو\n\n"
            f"🔗 لینک اختصاصی: {referral_link(uid)}\n"
            f"📨 ورود با لینک تو: {my_visits} نفر\n"
            f"✅ عضویت تأییدشده برای چالش: {challenge_count}/2 نفر\n"
            f"{challenge_status}\n\n"
            f"🛒 مشتری موفق از خرید: {len(successful)} نفر\n"
            f"🎁 جایزه‌های خرید قابل دریافت: {pending} عدد"
        )
    if d=='ref_claim':
        await q.answer()
        data=load_referrals(); rid=str(uid); pending=int(data.get('pending_rewards',{}).get(rid,0) or 0)
        if pending<=0:
            return await q.answer('❌ جایزه قابل دریافت نداری.',show_alert=True)
        await q.message.reply_text('⏳ در حال ساخت جایزه ۱۰GB از V2Route...')
        reward={
            'id':f'REF-{uid}-{int(datetime.now().timestamp())}',
            'user_id':uid,'service':'V2Ray','v2ray_tier':'اقتصادی',
            'volume':'10GB','duration':'1 ماهه','price':0,'status':'reward',
            'created_at':datetime.now().isoformat()
        }
        url,err=await v2route_create_service(reward)
        if not url:
            return await q.message.reply_text('❌ ساخت جایزه ناموفق بود.\n\n'+str(err))
        data['pending_rewards'][rid]=pending-1
        save_referrals(data)
        orders=load_orders(); orders[reward['id']]=reward; save_orders(orders)
        await q.message.reply_text(
            '🎁 جایزه‌ات آماده شد!\n\n'
            '📦 حجم: 10GB\n'
            '📅 مدت: 1 ماه\n'
            '🌐 نوع: V2Ray اقتصادی\n\n'
            '🔗 لینک اشتراک:\n'+str(url))
        if reward.get('v2route_qr'):
            try: await send_vynexa_v2route_qr(context,uid,reward.get('v2route_qr'))
            except Exception: pass
        return
    if d.startswith('ref_admin:'):
        if not is_admin(uid): return await q.answer('⛔ فقط مدیر.',show_alert=True)
        rid=d.split(':',1)[1]; data=load_referrals(); bucket=data.get('successful_customers',{}).get(rid,{})
        challenge=data.get("challenge_successful",{}).get(rid,{})
        completion=data.get("challenge_completions",{}).get(rid)
        lines=[
            f'👤 معرف: {rid}',
            f'🛒 مشتری موفق از خرید: {len(bucket)} نفر',
            f'🎁 جایزه خرید قابل دریافت: {int(data.get("pending_rewards",{}).get(rid,0) or 0)}',
            f'🏁 دعوت تأییدشده برای چالش: {len(challenge)}/2',
            f'📌 وضعیت چالش: {"تکمیل‌شده ✅" if completion else "در حال انجام"}',
            ''
        ]
        if completion:
            lines.append(f'🗓 زمان تکمیل: {completion.get("completed_at", "-")}')
        if challenge:
            lines.append('👥 دعوت‌شده‌های تأییدشده:')
            for cid,v in list(challenge.items())[-50:]:
                lines.append(f'• {cid} | {v.get("at", "-")}')
        if bucket:
            lines.append('\n🛒 خریدهای موفق:')
            for cid,v in list(bucket.items())[-30:]:
                lines.append(f'• {cid} | سفارش: {v.get("order_id","-")}')
        return await q.message.reply_text(
            '\n'.join(lines),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "👤 مشاهده پروفایل معرف",
                    url=f"tg://user?id={rid}"
                )
            ]])
        )

def find_token():
    for p in (HOME / 'bot_old_backup.py', HOME / 'bot_before_v3.py', HOME / 'bot.py'):
        if p.exists():
            s = p.read_text(encoding='utf-8', errors='ignore')
            m = re.search(r'^TOKEN\s*=\s*[\'\"]([^\'\"]+)[\'\"]', s, re.M)
            if m and ':' in m.group(1):
                return m.group(1)
    c = load_config()
    return c.get('token') or c.get('TOKEN')


def admin_id():
    if ADMIN_ID_FILE.exists():
        try:
            return int(ADMIN_ID_FILE.read_text().strip())
        except Exception:
            pass
    c = load_config()
    for k in ('admin_id', 'ADMIN_ID'):
        if str(c.get(k, '')).isdigit():
            return int(c[k])
    return 0


def set_admin(uid):
    ADMIN_ID_FILE.write_text(str(uid), encoding='utf-8')
    c = load_config(); c['admin_id'] = int(uid); save_config(c)


def is_admin(uid):
    return admin_id() != 0 and int(uid) == admin_id()


def bot_enabled():
    return bool(load_config().get('bot_enabled', True))


PRICE_MARKUP = 1.20

def money(x):
    try: return f'{int(x):,} تومان'
    except Exception: return str(x)

def shown_price(x):
    try: return money(int(round(int(x) * PRICE_MARKUP)))
    except Exception: return money(x)


def _button_style(label):
    """رنگ دکمه‌ها با قابلیت رسمی Telegram Bot API 9.4."""
    text = str(label).strip().lower()
    # قرمز: برگشت، لغو و عملیات حذف
    if any(word in text for word in ('برگشت', 'بازگشت', 'لغو', 'حذف', 'رد کردن', '❌ رد')):
        return 'danger'
    # آبی: بخش‌های اطلاعاتی و ناوبری
    if any(word in text for word in ('سرویس‌های من', 'سرویس مشتری', 'سرویس‌های تأیید', 'اطلاعیه', 'پشتیبانی', 'درخواست نمایندگی', 'مشاهده', 'اطلاعات', 'خروج به صفحه')):
        return 'primary'
    # سبز: خرید، پرداخت، کیف پول و انتخاب‌های اصلی
    if any(word in text for word in ('خرید', 'کیف پول', 'تمدید', 'تست', 'دریافت', 'تأیید', 'ارسال کانفیگ', 'گردان شانس', 'گردونه شانس', 'زیرمجموعه‌گیری', 'سوالات هوش مصنوعی', 'حساب کاربری')):
        return 'success'
    return None


def kb(rows):
    # سرعت: config فقط یک‌بار برای کل منو خوانده می‌شود، نه برای تک‌تک دکمه‌ها.
    keyboard = []
    try:
        cfg = load_config()
        custom_ids = cfg.get('button_custom_emojis', {}) or {}
        text_emojis = cfg.get('button_custom_emoji_text', {}) or {}
    except Exception:
        custom_ids, text_emojis = {}, {}
    for row in rows:
        styled_row = []
        for label in row:
            label = str(label)
            style = _button_style(label)
            kwargs = {'callback_data': 'menu:' + label}
            if style:
                kwargs['style'] = style
            shown_label = label
            try:
                icon_id = str(custom_ids.get(label, '')).strip()
                if icon_id.isdigit():
                    kwargs['icon_custom_emoji_id'] = icon_id
                text_emoji = str(text_emojis.get(label, '')).strip()
                if text_emoji:
                    shown_label = f'{text_emoji} {label}'
            except Exception:
                pass
            styled_row.append(InlineKeyboardButton(shown_label, **kwargs))
        keyboard.append(styled_row)
    return InlineKeyboardMarkup(keyboard)


def home(uid):
    rows = [['🛒 خرید سرویس', '🔄 تمدید سرویس'], ['📦 سرویس‌های من', '🎧 پشتیبانی'], ['💰 کیف پول'], ['🌐 پروکسی تلگرام'], ['🎲 گردان شانس'], ['👥 زیرمجموعه‌گیری'], ['🤖 سوالات هوش مصنوعی']]
    if is_admin(uid):
        rows += [['📢 اطلاعیه', '🤖 ربات روشن/خاموش']]
    return kb(rows)


def admin_panel():
    return kb([
        ['📦 سرویس‌های تأیید شده'],
        ['👥 سرویس مشتری‌ها'],
        ['🚀 ارسال کانفیگ'],
        ['👥 زیرمجموعه‌گیری'],
        ['🎲 گردونه شانس'],
        ['📢 ارسال پیام به کانال'],
        ['🔙 خروج به صفحه اصلی'],
    ])


def prices_menu():
    prices = load_config().get('prices', {})
    names = []
    for name, item in prices.items():
        if not isinstance(item, dict):
            continue
        lname = str(name).lower()
        # WireGuard/OpenVPN are always available in the customer menu.
        if lname in ('wireguard', 'openvpn') or item.get('active', True):
            if lname == 'v2ray':
                names.insert(0, str(name))
            else:
                names.append(str(name))
    rows = [[('🌐 V2Ray' if str(name).lower() == 'v2ray' else ('🟢 WireGuard' if str(name).lower() == 'wireguard' else ('🔵 OpenVPN' if str(name).lower() == 'openvpn' else ('🟢 ' + str(name)))))] for name in names]
    rows.append(['🔙 برگشت'])
    return kb(rows or [['❌ فعلاً VPN فعالی ثبت نشده'], ['🔙 برگشت']])


def order_summary(o):
    identity = o.get('name') if o.get('identity_type') == 'name' else o.get('phone')
    return (
        '🧾 فاکتور سفارش\n\n'
        f'👤 اطلاعات مشتری: {identity or "-"}\n'
        f'🌐 سرویس: {o.get("service", "-")}\n'
        f'📦 حجم: {o.get("volume", "-")}\n'
        f'⏳ مدت: {o.get("duration", "-")}\n'
        f'🚀 سرعت: {o.get("speed", "-")}\n'
        f'💰 مبلغ: {money(o.get("price", 0))}\n'
        f'🆔 سفارش: {o.get("id", "-")}'
    )


def remember_user(uid):
    now = datetime.now()
    users = load_users(); key = str(uid)
    u = users.setdefault(key, {'user_id': uid, 'wallet': 0, 'created_at': now.isoformat()})
    last = u.get('last_seen', '')
    save_needed = True
    if last:
        try:
            save_needed = (now - datetime.fromisoformat(last)).total_seconds() >= 60
        except Exception:
            save_needed = True
    if save_needed:
        u['last_seen'] = now.isoformat()
        save_users(users)


def add_wallet(uid, amount):
    users = load_users(); key = str(uid)
    users.setdefault(key, {'user_id': uid, 'wallet': 0})
    users[key]['wallet'] = int(users[key].get('wallet', 0)) + int(amount)
    save_users(users)
    return users[key]['wallet']


def wallet_balance(uid):
    return int(load_users().get(str(uid), {}).get('wallet', 0))


def make_order_id():
    return datetime.now().strftime('%Y%m%d%H%M%S%f')



async def record_challenge_join(context, referred_uid):
    """ثبت جداگانه دعوت‌های چالش؛ بدون صدور جایزه یا سرویس."""
    uid = str(referred_uid)
    data = load_referrals()
    attr = data.setdefault("users", {}).get(uid)
    if not attr:
        return

    rid = str(attr.get("referrer_id", ""))
    if not rid or rid == uid or not rid.isdigit():
        return

    all_invites = data.setdefault("challenge_successful", {})
    bucket = all_invites.setdefault(rid, {})
    if uid in bucket:
        return

    bucket[uid] = {"at": datetime.now().isoformat()}
    completions = data.setdefault("challenge_completions", {})
    newly_completed = len(bucket) >= 2 and rid not in completions

    if newly_completed:
        invitees = list(bucket.keys())[:2]
        completions[rid] = {
            "completed_at": datetime.now().isoformat(),
            "invitees": invitees,
        }

    save_referrals(data)

    if newly_completed:
        # پیام تبریک برای معرف؛ فقط یک‌بار در زمان تکمیل چالش
        try:
            await context.bot.send_message(
                chat_id=int(rid),
                text=(
                    "🎉 دمت گرم! 💙🔥\n"
                    "۲ تا زیرمجموعه‌ات تکمیل شد! حالا وقتشه وارد قرعه‌کشی بشی! 🎁\n\n"
                    "📸 از همین پیام اسکرین‌شات بگیر و به پشتیبانی بفرست:\n"
                    "👉 @vynexavpn1\n\n"
                    "💬 یا توی گپ وینکسا بفرست:\n"
                    "https://t.me/vynexagp\n\n"
                    "🍀 شانس برنده شدنت رو از دست نده! 💙"
                ),
                disable_web_page_preview=True,
            )
        except Exception as e:
            print("CHALLENGE USER CONGRATS ERROR:", repr(e))

        # گزارش تکمیل برای ادمین، همراه دکمه مشاهده پروفایل معرف
        try:
            await context.bot.send_message(
                chat_id=admin_id(),
                text=(
                    "🏁 تکمیل چالش زیرمجموعه‌گیری\n\n"
                    f"🆔 آیدی عددی معرف: {rid}\n"
                    "👥 دو کاربر متفاوت عضویت کانال @VynexaVPN را تأیید کردند.\n"
                    f"🆔 دعوت‌شده‌ها: {invitees[0]} و {invitees[1]}\n"
                    "💾 نتیجه در بخش زیرمجموعه‌گیری ذخیره شد.\n"
                    "🎁 جایزه یا سرویسی خودکار صادر نشده است."
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "👤 مشاهده پروفایل معرف",
                        url=f"tg://user?id={rid}"
                    )
                ]]),
            )
        except Exception as e:
            print("CHALLENGE ADMIN REPORT ERROR:", repr(e))


async def _delete_message_after_delay(bot, chat_id, message_id, delay=30):
    try:
        await asyncio.sleep(delay)
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as exc:
        print("VYNEXA DELAYED MESSAGE DELETE ERROR:", repr(exc))


async def force_join_gate(update, context):
    from telegram.ext import ApplicationHandlerStop
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat or chat.type != "private":
        return

    # ذخیره معرف از همان لینک اولیه، حتی اگر کاربر هنوز عضو نشده باشد.
    incoming = str(getattr(update.message, "text", "") or "").split()
    if len(incoming) > 1 and incoming[0].split("@")[0] == "/start":
        token = incoming[1]
        if token.startswith("ref_") and token[4:].isdigit():
            # فقط کاربرانی که قبلاً در دیتابیس ربات ثبت نشده‌اند.
            known_users = load_users()
            already_known = str(user.id) in known_users
            if not already_known:
                referrer_id = int(token[4:])
                is_new = register_referral_visit(user.id, referrer_id)
            else:
                is_new = False
            if is_new:
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=(
                            "🔔 یک نفر با لینک زیرمجموعه‌گیری تو وارد ربات شد! 💙\n\n"
                            f"🆔 آیدی عددی: {user.id}\n"
                            "📌 برای ثبت دعوت در چالش، باید عضو کانال @VynexaVPN هم بشه."
                        )
                    )
                except Exception as e:
                    print("REFERRAL ARRIVAL NOTICE ERROR:", repr(e))

    query = update.callback_query
    checking = bool(query and query.data == "check_membership")
    now = datetime.now().timestamp()

    # Successful checks are cached for 5 minutes. This prevents a Telegram API
    # request on every message, which was causing the bot to appear frozen.
    if (context.user_data.get("membership_cache_joined")
        and context.user_data.get("membership_cache_until", 0) > now
        and not checking):
        return

    try:
        joined = True
        for required_chat in (JOIN_CHANNEL_ID,):
            member = await asyncio.wait_for(
                context.bot.get_chat_member(required_chat, user.id),
                timeout=12.0
            )
            is_member = member.status in ("creator", "administrator", "member")
            if member.status == "restricted":
                is_member = bool(getattr(member, "is_member", False))
            if not is_member:
                joined = False
    except Exception as e:
        # Fail open on Telegram API/network errors: never trap the user behind
        # a temporary membership-check failure or block every inline menu click.
        print("Force join check temporarily unavailable:", repr(e)[:160])
        if checking and query:
            try:
                await query.answer()
            except Exception:
                pass
            try:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text="🏠 منوی اصلی",
                    reply_markup=home(user.id),
                )
            except Exception:
                pass
            raise ApplicationHandlerStop
        # Let normal handlers (including /start and inline-menu routing) continue.
        return

    if joined:
        context.user_data["membership_cache_joined"] = True
        context.user_data["membership_cache_until"] = now + 300
        await record_challenge_join(context, user.id)
        if checking and query:
            await query.answer("عضویت تأیید شد ✅")
            await context.bot.send_message(
                chat_id=chat.id,
                text="✅ عضویتت تأیید شد! حالا /start رو بزن."
            )
            raise ApplicationHandlerStop
        return

    context.user_data["membership_cache_joined"] = False
    context.user_data["membership_cache_until"] = 0
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 عضویت در کانال", url="https://t.me/VynexaVPN")],
        [InlineKeyboardButton("✅ بررسی عضویت", callback_data="check_membership")]
    ])
    if checking and query:
        await query.answer("هنوز عضویتت تأیید نشده؛ اول عضو کانال شو.", show_alert=True)
    await context.bot.send_message(
        chat_id=chat.id,
        text="🔒 برای استفاده از ربات VynexaVPN ابتدا فقط عضو کانال @VynexaVPN شو:",
        reply_markup=keyboard
    )
    raise ApplicationHandlerStop


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    remember_user(uid)

    # Remove the old bottom ReplyKeyboard that Telegram may have cached from
    # an earlier version. Inline buttons are unaffected.
    try:
        old_keyboard_msg = await update.effective_message.reply_text(
            "⌨️", reply_markup=ReplyKeyboardRemove()
        )
        await old_keyboard_msg.delete()
    except Exception:
        pass

    arg = str(context.args[0]).strip() if context.args else ""

    # لینک‌های مستقیم کانال
    if arg.startswith('ref_') and arg[4:].isdigit():
        register_referral_visit(uid, int(arg[4:]))

    # در صورت ذخیره بودن معرف، بررسی تکراری بی‌خطر است.
    await record_challenge_join(context, uid)

    if not bot_enabled() and not is_admin(uid):
        return await update.message.reply_text(
            '🔴 ربات فعلاً خاموش است.',
            reply_markup=home(uid)
        )

    # خرید سرویس
    if arg == 'buy':
        return await buy(update, context)

    # تست رایگان
    if arg == 'test':
        return await v2ray_test_menu(update, context)

    # گردونه شانس
    if arg == 'dice':
        return await vynexa_dice(update, context)

    # پشتیبانی
    if arg == 'support':
        return await support(update, context)

    await update.message.reply_text(WELCOME, reply_markup=home(uid))


async def admin_cmd(update, context):
    uid = update.effective_user.id
    # Preserve an existing admin ID. If none exists, the first /admin claims the panel.
    if admin_id() == 0:
        set_admin(uid)
    if not is_admin(uid):
        return await update.message.reply_text('⛔ این بخش فقط برای مدیر است.')
    context.user_data['admin_mode']=True
    await update.message.reply_text('🛠 پنل مدیریت', reply_markup=admin_panel())


async def buy(update, context):
    if not bot_enabled() and not is_admin(update.effective_user.id):
        return await update.message.reply_text('🔴 ربات فعلاً خاموش است.')
    context.user_data.clear()
    await update.message.reply_text('🌐 VPN موردنظر را انتخاب کن:', reply_markup=prices_menu())


async def show_invoice_then_identity(update, context):
    o = context.user_data.get("order", {})

    service = o.get("service", "-")
    volume = o.get("volume", "-")
    duration = o.get("duration", "-")
    speed = o.get("speed", "-")
    if not o.get("price_markup_applied"):
        o["price"] = int(round(int(o.get("price", 0)) * PRICE_MARKUP))
        o["price_markup_applied"] = True
        o["price_markup_rate"] = PRICE_MARKUP
        context.user_data["order"] = o
    price = int(o.get("price", 0))
    tier = o.get("v2ray_tier")

    tier_line = ""
    if tier:
        tier_line = f"📊 نوع سرویس: {o.get('v2ray_tier_display', tier)}\n"

    invoice = (
        "🧾 فاکتور سفارش\n\n"
        f"🌐 سرویس: {service} ✨\n"
        f"{tier_line}"
        f"📦 حجم/پلن: {volume} 📦\n"
        f"⏳ مدت: {duration} ⏱️\n"
        f"🚀 سرعت: {speed} ⚡\n"
        f"💰 مبلغ: {money(price)} 💳\n\n"
        "🔎 لطفاً فاکتور را بررسی کن."
    )

    context.user_data['awaiting_invoice_confirmation'] = True
    context.user_data['invoice_confirmed'] = False
    return await update.message.reply_text(
        invoice + "\n\n✅ اگر مشخصات و مبلغ درست است، فاکتور را تأیید کن.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton('✅ تأیید فاکتور و ادامه', callback_data='invoiceconfirm:yes')],
            [InlineKeyboardButton('❌ لغو سفارش', callback_data='invoiceconfirm:no')]
        ])
    )

async def choose_vpn(update, context, name):
    if str(name).lower() == 'v2ray':
        return await v2ray_menu(update, context)
    prices = load_config().get('prices', {})
    item = prices.get(name)
    if not isinstance(item, dict):
        for k, v in prices.items():
            if str(k).lower() == str(name).lower() and isinstance(v, dict):
                name = k; item = v; break
    if not isinstance(item, dict):
        return await update.message.reply_text('❌ اطلاعات این VPN پیدا نشد.')
    lname = str(name).lower()
    if lname not in ('wireguard', 'openvpn') and not item.get('active', True):
        return await update.message.reply_text('❌ این VPN فعال نیست.')
    context.user_data['service'] = name; context.user_data['item'] = item
    # WireGuard: 1 month -> speed -> invoice -> identity
    if lname == 'wireguard':
        speeds = []
        for plan, value in item.items():
            if isinstance(value, (int, float)):
                speeds.append([f'⚡ 1 ماهه | 🚀 {plan} — {shown_price(value)}'])
        speeds.append(['🔙 برگشت'])
        return await update.message.reply_text('🟢 WireGuard\n\n📅 مدت: ۱ ماهه\n🚀 سرعت را انتخاب کن:', reply_markup=kb(speeds))
    # Direct-price VPN
    if 'price' in item:
        context.user_data.update({
            'price': int(item.get('price', 0)),
            'volume': item.get('volume', '-'),
            'duration': item.get('duration', '-'),
            'speed': item.get('speed', '-')
        })
        context.user_data['order'] = {
            'id': make_order_id(), 'user_id': update.effective_user.id,
            'service': name, 'volume': item.get('volume', '-'),
            'duration': item.get('duration', '-'), 'speed': item.get('speed', '-'),
            'price': int(item.get('price', 0)), 'status': 'draft',
            'created_at': datetime.now().isoformat()
        }
        return await show_invoice_then_identity(update, context)
    rows = []
    for plan, value in item.items():
        if isinstance(value, (int, float)):
            rows.append([f'📦 {str(plan)}'])
    rows.append(['🔙 برگشت'])
    if len(rows) == 1:
        return await update.message.reply_text('❌ برای این VPN پلنی ثبت نشده است.')
    await update.message.reply_text(f'📦 پلن‌های {name}:', reply_markup=kb(rows))


def v2ray_item():
    prices = load_config().get('prices', {})
    for k, v in prices.items():
        if str(k).lower() == 'v2ray' and isinstance(v, dict):
            return v
    return {}


def fa_to_en_digits(text):
    return str(text).translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))


async def v2ray_menu(update, context):
    context.user_data.clear()
    context.user_data['v2ray_flow'] = True
    return await update.message.reply_text(
        '🌐 V2Ray\n\nنوع سرویس را انتخاب کن:',
        reply_markup=kb([['💚 اقتصادی-حجمی'], ['🔵 عادی-حجمی'], ['🟣 پرو- نامحدود حجم'], ['🧪 تست رایگان'], ['🔙 برگشت']])
    )


async def v2ray_duration_menu(update, context, tier):
    context.user_data['v2ray_flow'] = True
    context.user_data['v2ray_tier'] = tier
    if tier == 'pro':
        return await update.message.reply_text('🟣 پرو — نامحدود حجم\n\nتعداد کاربران را انتخاب کن:', reply_markup=kb([['👤 تک کاربر'], ['👥 چند کاربر'], ['🔙 برگشت']]))
    return await update.message.reply_text(
        f'🔹 {"اقتصادی" if tier == "economic" else "عادی"}\n\nمدت سرویس را انتخاب کن:',
        reply_markup=kb([['📅 1 ماهه'], ['📅 3 ماهه'], ['🔙 برگشت']])
    )


async def v2ray_volume_menu(update, context):
    tier = context.user_data.get('v2ray_tier')
    duration = context.user_data.get('v2ray_duration')
    data = v2ray_item().get(tier, {})
    if duration == '1 ماهه' and tier in ('economic', 'normal'):
        vals = {'economic': [45000,50000,55000,60000,65000,70000], 'normal': [75000,84000,93000,102000,111000,120000]}[tier]
        rows = [[f'📦 {gb}GB — {shown_price(price)}'] for gb, price in zip(range(5,11), vals)]
        rows.append(['📦 حجم دلخواه (۵GB به بالا)'])
        rows.append(['🔙 برگشت'])
        return await update.message.reply_text('📦 حجم سرویس را انتخاب کن:', reply_markup=kb(rows))
    if duration == '3 ماهه':
        rows=[]
        for volume, price in data.get('3 ماهه', {}).items():
            rows.append([f'📦 {volume} — {shown_price(price)}'])
        rows.append(['🔙 برگشت'])
        return await update.message.reply_text('📦 حجم سرویس را انتخاب کن:', reply_markup=kb(rows))
    if tier == 'pro':
        return await create_v2ray_order(update, context, 'نامحدود', 220000, '1 ماهه')


def v2ray_custom_price(tier, gb):
    if tier == 'economic':
        base = 45000 + (gb - 5) * 5000 if gb <= 10 else gb * 6000
    else:
        base = 75000 + (gb - 5) * 9000 if gb <= 10 else gb * 10000
    return int(round(base * PRICE_MARKUP))


async def show_v2ray_custom_timeline(message, context, gb, edit=False):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    gb = max(5, min(1000, int(gb)))
    context.user_data['v2ray_custom_gb'] = gb
    tier = context.user_data.get('v2ray_tier', 'economic')
    price = v2ray_custom_price(tier, gb)
    text = (
        '📦 انتخاب حجم دلخواه VynexaVPN\n\n'
        f'💾 حجم انتخابی: {gb:,} گیگابایت\n'
        f'💰 قیمت: {money(price)}\n\n'
        'با دکمه‌ها حجم را کم‌وزیاد کن؛ حداقل ۵ و حداکثر ۱۰۰۰ گیگابایت.'
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton('−100 GB', callback_data='v2custom:step:-100'), InlineKeyboardButton('−25 GB', callback_data='v2custom:step:-25'), InlineKeyboardButton('−5 GB', callback_data='v2custom:step:-5')],
        [InlineKeyboardButton('+5 GB', callback_data='v2custom:step:5'), InlineKeyboardButton('+25 GB', callback_data='v2custom:step:25'), InlineKeyboardButton('+100 GB', callback_data='v2custom:step:100')],
        [InlineKeyboardButton('✅ تأیید حجم', callback_data='v2custom:confirm')],
        [InlineKeyboardButton('🔙 برگشت', callback_data='v2custom:back')]
    ])
    if edit:
        try:
            return await message.edit_text(text, reply_markup=keyboard, parse_mode='Markdown')
        except Exception:
            return await message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
    return await message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')


async def create_v2ray_order(update, context, volume, price, duration):
    uid = update.effective_user.id
    tier = context.user_data.get('v2ray_tier', '')
    labels = {'economic':'اقتصادی-حجمی','normal':'عادی-حجمی','pro':'پرو- نامحدود حجم'}
    backend_labels = {'economic':'اقتصادی','normal':'عادی','pro':'پرو'}
    o = {
        'id': make_order_id(), 'user_id': uid, 'service': 'V2Ray',
        'v2ray_tier': backend_labels.get(tier, tier), 'v2ray_tier_display': labels.get(tier, tier), 'volume': str(volume),
        'duration': duration, 'speed': '-', 'price': int(price),
        'status': 'draft', 'created_at': datetime.now().isoformat()
    }
    context.user_data['order'] = o
    context.user_data.pop('v2ray_wait_custom', None)
    return await show_invoice_then_identity(update, context)


async def v2ray_test_menu(update, context):
    context.user_data.clear()
    context.user_data['v2ray_flow'] = True
    return await update.message.reply_text(
        '🧪 تست رایگان V2Ray\n\nنوع تست را انتخاب کن:',
        reply_markup=kb([['🧪 تست اقتصادی'], ['🧪 تست عادی'], ['🟣 تست پرو'], ['🔙 برگشت']])
    )


async def handle_v2ray_test(update, context, tier):
    uid = update.effective_user.id
    users = load_users()
    user = users.setdefault(str(uid), {})

    if tier == "pro":
        return await update.message.reply_text(
            f"🟣 تست پرو خودکار ارسال نمی‌شود.\\n\\nپشتیبانی: {SUPPORT}",
            reply_markup=kb([["🔙 برگشت"]])
        )

    if tier not in ("economic", "normal"):
        return await update.message.reply_text(
            "نوع تست نامعتبر است.", reply_markup=kb([["🔙 برگشت"]])
        )

    flag = "v2ray_economic_test_used" if tier == "economic" else "v2ray_normal_test_used"
    if user.get(flag):
        return await update.message.reply_text(
            "❌ قبلاً تست این نوع را دریافت کرده‌ای.",
            reply_markup=kb([["🔙 برگشت"]])
        )

    order_id = f"TEST-{uid}-{tier}"
    order = {
        "id": order_id,
        "v2ray_tier": "اقتصادی" if tier == "economic" else "عادی",
        "duration": "1 ماهه",
        "volume": "0.1GB",
    }

    link, error = await v2route_create_service(order)
    if not link:
        print("V2Route test creation failed:", str(error)[:300])
        return await update.message.reply_text(
            "❌ ساخت تست از پنل ناموفق شد. تنظیمات API و گزارش Termux را بررسی کن.",
            reply_markup=kb([["🔙 برگشت"]])
        )

    c = load_config()
    tests = c.setdefault("v2ray_tests", {})
    history = tests.setdefault(
        "used_economic" if tier == "economic" else "used_normal", []
    )
    history.append({
        "user_id": uid,
        "link": str(link),
        "used_at": datetime.now().isoformat(),
        "panel_order_id": order_id,
        "volume_gb": 0.1,
    })

    user[flag] = True
    save_config(c)
    save_users(users)

    label = "اقتصادی" if tier == "economic" else "عادی"
    return await update.message.reply_text(
        f"✅ تست {label} ساخته شد.\n📦 حجم: 0.1 گیگابایت\n\n🔗 لینک اشتراک:\n{link}",
        reply_markup=kb([["🔙 برگشت"]])
    )


async def services(update, context):
    """Send each owned service in its own message; never edit the clicked menu."""
    uid = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    orders = load_orders()
    mine = [
        (oid, o) for oid, o in orders.items()
        if str(o.get('user_id')) == uid
        and o.get('status') in ('paid', 'delivered', 'confirmed')
    ]
    await context.bot.send_message(chat_id=chat_id, text='📦 سرویس‌های ثبت‌شده برای شما:')
    if not mine:
        return await context.bot.send_message(
            chat_id=chat_id,
            text='📦 هنوز سرویسی برای شما ثبت نشده است.'
        )
    for oid, o in mine:
        text = order_summary(o)
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton('🔐 دریافت اطلاعات', callback_data=f'info:{oid}')],
            [InlineKeyboardButton('🗑 حذف سرویس', callback_data=f'del:{oid}')],
            [InlineKeyboardButton('❌ کار نمی‌کند', callback_data=f'bad:{oid}')],
        ])
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)


# ===== LIVE V2ROUTE SERVICE INFO =====
async def v2route_live_info(o):
    """دریافت حجم مصرفی و تاریخ انقضا از لینک Subscription"""
    import httpx

    url = o.get('subscription_url')

    # اگر subscription_url ذخیره نشده بود، از delivery پیدا کن
    if not url:
        for x in o.get('delivery', []):
            if not isinstance(x, dict):
                continue
            if x.get('type') == 'text':
                value = str(x.get('value', '')).strip()
                if value.startswith(('http://', 'https://')):
                    url = value
                    break

    if not url:
        return None, 'لینک اشتراک این سرویس پیدا نشد.'

    try:
        # Live statistics are optional: keep DNS/network failures from making
        # the bot feel frozen. Short connect/read timeouts keep callbacks snappy.
        timeout = httpx.Timeout(4.0, connect=1.5, read=3.0, write=2.0, pool=1.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        ) as client:
            r = await client.get(url)

        if not r.is_success:
            return None, f'خطای دریافت اشتراک: HTTP {r.status_code}'

        info = (
            r.headers.get('subscription-userinfo')
            or r.headers.get('Subscription-Userinfo')
        )

        if not info:
            return None, 'اطلاعات مصرف زنده در پاسخ اشتراک وجود ندارد.'

        vals = {}

        for part in info.split(';'):
            if '=' in part:
                k, v = part.strip().split('=', 1)
                vals[k.strip().lower()] = v.strip()

        def to_int(x):
            try:
                return int(float(x))
            except:
                return 0

        total = to_int(vals.get('total', 0))
        upload = to_int(vals.get('upload', 0))
        download = to_int(vals.get('download', 0))

        used = upload + download
        remaining = max(0, total - used)

        expire = to_int(vals.get('expire', 0))

        return {
            'total': total,
            'upload': upload,
            'download': download,
            'used': used,
            'remaining': remaining,
            'expire': expire
        }, None

    except Exception as e:
        print('LIVE V2ROUTE ERROR:', repr(e))
        return None, 'خطا در دریافت اطلاعات زنده: ' + str(e)


def bytes_to_gb(value):
    try:
        return float(value) / (1024 ** 3)
    except:
        return 0


def format_gb(value):
    try:
        gb = bytes_to_gb(value)

        if gb >= 100:
            return f'{gb:.0f} GB'
        if gb >= 10:
            return f'{gb:.1f} GB'

        return f'{gb:.2f} GB'

    except:
        return '-'


def live_service_text(o, info):

    if not info:
        return order_summary(o)

    total = info.get('total', 0)
    upload = info.get('upload', 0)
    download = info.get('download', 0)
    used = info.get('used', 0)
    remaining = info.get('remaining', 0)
    expire = info.get('expire', 0)

    if expire:
        try:
            # بعضی سرویس‌ها میلی‌ثانیه می‌دهند
            ts = expire / 1000 if expire > 10000000000 else expire

            dt = datetime.fromtimestamp(ts)

            expiry_text = dt.strftime('%Y/%m/%d - %H:%M')

            days = max(
                0,
                int((ts - datetime.now().timestamp()) / 86400)
            )

        except:
            expiry_text = '-'
            days = '-'
    else:
        expiry_text = '-'
        days = '-'

    if expire:
        try:
            status = '🟢 فعال' if days != 0 else '🔴 منقضی'
        except:
            status = '🟢 فعال'
    else:
        status = '🟢 فعال'

    name = (
        o.get('name')
        or o.get('phone')
        or '-'
    )

    return (
        '📊 اطلاعات زنده سرویس\n'
        '\n'
        f'👤 نام: {name}\n'
        f'🌐 سرویس: {o.get("service", "V2Ray")}\n'
        '\n'
        '━━━━━━━━━━━━━━━━━━\n'
        f'📦 حجم کل: {format_gb(total)}\n'
        f'📉 حجم استفاده‌شده: {format_gb(used)}\n'
        f'📤 آپلود: {format_gb(upload)}\n'
        f'📥 دانلود: {format_gb(download)}\n'
        f'💾 حجم باقی‌مانده: {format_gb(remaining)}\n'
        '━━━━━━━━━━━━━━━━━━\n'
        f'📅 تاریخ انقضا: {expiry_text}\n'
        f'⏳ روز باقی‌مانده: {days} روز\n'
        f'🔰 وضعیت: {status}\n'
        '\n'
        '🔄 اطلاعات همین الان از اشتراک دریافت شد.'
    )


# ===== SERVICE RENEWAL =====
def customer_services_for_renewal(uid):
    orders = load_orders()
    out = []
    for oid, o in orders.items():
        if str(o.get('user_id')) != str(uid):
            continue
        if o.get('type') == 'renewal':
            continue
        if o.get('status') not in ('paid', 'delivered', 'confirmed'):
            continue
        if str(o.get('service', '')).lower() != 'v2ray':
            continue
        out.append((oid, o))
    return out


def renewal_identity(o):
    return str(o.get('name') or o.get('phone') or '').strip()


async def renew_start(update, context):
    uid = update.effective_user.id
    mine = customer_services_for_renewal(uid)
    if not mine:
        return await update.message.reply_text(
            '🔄 تمدید سرویس\n\n❌ هنوز سرویس V2Ray قابل تمدیدی برای شما ثبت نشده است.',
            reply_markup=home(uid)
        )
    context.user_data.clear()
    context.user_data['renew_wait_name'] = True
    context.user_data['_menu_force_new_messages'] = 'first'
    try:
        await update.message.reply_text('🔄 تمدید سرویس\n\n📦 سرویس‌های قابل تمدیدت:')
        for i, (oid, o) in enumerate(mine, 1):
            ident = renewal_identity(o) or 'بدون نام'
            await update.message.reply_text(
                f'{i}. {ident}\n🌐 سرویس: {o.get("service", "-")}\n'
                f'📦 حجم: {o.get("volume", "-")}\n⏳ مدت: {o.get("duration", "-")}'
            )
        return await update.message.reply_text(
            '✏️ حالا نام سرویس موردنظرت را دقیقاً ارسال کن:',
            reply_markup=kb([['🔙 برگشت']])
        )
    finally:
        context.user_data.pop('_menu_force_new_messages', None)


async def show_renewal_confirmation(update, context, o, oid):
    context.user_data['renew_selected_oid'] = oid
    price = int(o.get('price', 0))
    text = (
        '🔄 تأیید تمدید سرویس\n\n'
        f'👤 نام سرویس: {renewal_identity(o) or "-"}\n'
        f'🌐 سرویس: {o.get("service", "-")}\n'
        f'📦 حجم: {o.get("volume", "-")}\n'
        f'⏳ مدت تمدید: {o.get("duration", "-")}\n'
        f'💰 مبلغ تمدید: {money(price)}\n\n'
        '⚠️ با تأیید، همین اشتراک موجود تمدید می‌شود و لینک اشتراک جدیدی ساخته نخواهد شد.\n\n'
        'آیا تمدید را تأیید می‌کنی؟'
    )
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    return await msg.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton('✅ تأیید تمدید', callback_data=f'renewyes:{oid}'),
            InlineKeyboardButton('❌ رد', callback_data=f'renewno:{oid}')
        ]])
    )


async def renewal_payment_menu(update, context):
    o = context.user_data.get('order')
    if not o:
        return
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    await msg.reply_text(
        '💳 صفحه پرداخت تمدید سرویس\n\n' + order_summary(o) + '\n\nروش پرداخت را انتخاب کن:',
        reply_markup=kb([
            ['💳 کارت به کارت', '💰 استفاده از کیف پول'],
            ['🎟 کد تخفیف دارم'],
            ['🔙 برگشت']
        ])
    )


async def create_renewal_order(update, context, oid):
    orders = load_orders(); old = orders.get(oid)
    if not old:
        msg = update.message or (update.callback_query.message if update.callback_query else None)
        return await msg.reply_text('❌ سرویس پیدا نشد.')
    uid = update.effective_user.id
    o = {
        'id': make_order_id(), 'user_id': uid, 'type': 'renewal',
        'service': old.get('service', 'V2Ray'),
        'v2ray_tier': old.get('v2ray_tier', ''),
        'volume': old.get('volume', '-'), 'duration': old.get('duration', '1 ماهه'),
        'speed': old.get('speed', '-'), 'price': int(round(int(old.get('price', 0)) / float(old.get('price_markup_rate', 1.20) or 1.20) * PRICE_MARKUP)), 'price_markup_applied': True, 'price_markup_rate': PRICE_MARKUP,
        'status': 'draft', 'original_order_id': oid,
        'renew_identity': renewal_identity(old), 'created_at': datetime.now().isoformat()
    }
    # Keep the original customer identity for the payment/admin view.
    if old.get('identity_type') == 'phone':
        o['identity_type'] = 'phone'; o['phone'] = old.get('phone', '')
    else:
        o['identity_type'] = 'name'; o['name'] = old.get('name', '')
    context.user_data['order'] = o
    context.user_data['renewal_payment'] = True
    return await renewal_payment_menu(update, context)


async def v2route_renew_service(o):
    """Renew the existing V2Route client without creating a new subscription.

    The reseller create endpoint is known from the current integration. V2Route's
    public site documents renewal in the panel but does not publish the reseller
    renewal route, so this uses the conventional /clients/{id}/renew route.
    The client id can come from the original order or be discovered by name.
    """
    import httpx
    if V2ROUTE_TOKEN == 'PASTE_V2ROUTE_TOKEN_HERE':
        return False, 'V2Route Token وارد نشده است.'
    original_id = str(o.get('original_order_id', ''))
    orders = load_orders(); original = orders.get(original_id, {})
    client_id = original.get('v2route_client_id') or o.get('v2route_client_id')
    headers = {
        'Authorization': 'Bearer ' + V2ROUTE_TOKEN,
        'Content-Type': 'application/json',
        'Idempotency-Key': str(o['id']),
    }
    months = 3 if str(o.get('duration')) == '3 ماهه' else 1
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            if not client_id:
                r = await client.get(V2ROUTE_BASE + '/clients', headers=headers)
                try: data = r.json()
                except Exception: data = {'raw': r.text}
                print('V2ROUTE CLIENTS:', r.status_code, data)
                if not r.is_success:
                    return False, 'V2Route HTTP ' + str(r.status_code) + ': ' + str(data)
                clients = data.get('clients') if isinstance(data, dict) else data
                if not isinstance(clients, list):
                    clients = data.get('data', []) if isinstance(data, dict) else []
                if isinstance(clients, dict):
                    clients = list(clients.values())

                wanted = str(
                    original.get('name')
                    or original.get('phone')
                    or original.get('username')
                    or original.get('id')
                    or ''
                ).strip()

                possible = {
                    wanted,
                    str(original.get('id') or '').strip(),
                    'Vynexa-' + str(original.get('id') or '').strip()
                }
                possible = {x for x in possible if x}

                for c in clients:
                    if not isinstance(c, dict):
                        continue

                    values = []
                    for key in (
                        'id','client_id','uuid','name','username','email',
                        'remark','description','title'
                    ):
                        v = c.get(key)
                        if v is not None:
                            values.append(str(v).strip())

                    nested = c.get('client')
                    if isinstance(nested, dict):
                        for key in ('id','client_id','uuid','name','username','email'):
                            v = nested.get(key)
                            if v is not None:
                                values.append(str(v).strip())

                    if possible.intersection(values):
                        client_id = (
                            c.get('id')
                            or c.get('client_id')
                            or c.get('uuid')
                            or (nested.get('id') if isinstance(nested, dict) else None)
                            or (nested.get('client_id') if isinstance(nested, dict) else None)
                            or (nested.get('uuid') if isinstance(nested, dict) else None)
                        )
                        if client_id:
                            break

            if not client_id:
                return False, 'شناسه سرویس در V2Route پیدا نشد.'

            payload = {'months': months}

            # V2Route جدید: تمدید با شناسه رکورد پنل جدید
            renew_urls = [
                V2ROUTE_BASE + '/clients/' + str(client_id) + '/renew',
                V2ROUTE_BASE + '/clients/' + str(client_id) + '/extend',
            ]

            r = None
            last_data = None

            for renew_url in renew_urls:
                r = await client.post(
                    renew_url,
                    headers=headers,
                    json=payload
                )
                try:
                    last_data = r.json()
                except Exception:
                    last_data = {'raw': r.text}

                print('V2ROUTE RENEW TRY:', r.status_code, last_data)

                if r.is_success:
                    break

                # فقط برای خطای رکورد پیدا نشد، مسیر بعدی امتحان شود
                msg = str(last_data)
                if 'record not found' not in msg.lower():
                    break

            if r is None:
                return False, 'V2Route renewal request failed.'
            try: data = r.json()
            except Exception: data = {'raw': r.text}
            print('V2ROUTE RENEW:', r.status_code, data)
            if not r.is_success:
                return False, 'V2Route HTTP ' + str(r.status_code) + ': ' + str(data)
            return True, data
        except Exception as e:
            print('V2ROUTE RENEW ERROR:', repr(e))
            return False, repr(e)


async def support(update, context):
    await update.message.reply_text(
        f'🎧 پشتیبانی\n\nبرای ارتباط با پشتیبانی:\n{SUPPORT}',
        reply_markup=home(update.effective_user.id)
    )


async def wallet(update, context):
    b = wallet_balance(update.effective_user.id)
    await update.message.reply_text(
        f'💰 کیف پول شما\n\n💵 موجودی: {money(b)}',
        reply_markup=kb([['➕ شارژ کیف پول'], ['🔙 برگشت']])
    )


    # ===== VYNEXA DICE DISCOUNT =====
    entered_code = str(context.user_data.get("coupon_code","")).strip().upper()
    if entered_code.startswith("VX"):
        users=load_users()
        u=users.get(str(update.effective_user.id),{})
        rewards=u.get("dice_discount_rewards",[])
        reward=next((x for x in rewards if str(x.get("code","")).upper()==entered_code and not x.get("used")),None)

        if reward:
            context.user_data["dice_coupon"]=reward

async def discount_code_menu(update, context):
    o = context.user_data.get('order')
    if not o:
        return await update.message.reply_text('❌ سفارش فعالی پیدا نشد.')


    if o.get('discount_code'):
        return await update.message.reply_text('❌ کد تخفیف قبلاً برای این سفارش اعمال شده است.')

    context.user_data['waiting_discount'] = True
    context.user_data['waiting_discount_code'] = True
    return await update.message.reply_text(
        '🎟 کد تخفیف خود را وارد کنید:'
    )








async def _return_to_payment_menu(update, context, order, notice):
    """Show the updated payment choices by editing the last inline menu message."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    text = (str(notice).strip() + "\n\n" if notice else "") + order_summary(order) + "\n\nروش پرداخت را انتخاب کن:"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 کارت به کارت", callback_data="menu:💳 کارت به کارت")],
        [InlineKeyboardButton("💰 استفاده از کیف پول", callback_data="menu:💰 استفاده از کیف پول")],
        [InlineKeyboardButton("🎟 کد تخفیف دارم", callback_data="menu:🎟 کد تخفیف دارم")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="menu:🔙 برگشت")],
    ])

    chat_id = context.user_data.get("_last_inline_menu_chat_id")
    message_id = context.user_data.get("_last_inline_menu_message_id")
    if chat_id is not None and message_id is not None:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=markup,
            )
            return
        except Exception as exc:
            print("DISCOUNT MENU EDIT ERROR:", repr(exc))

    # Fallback for users who reached this flow through a regular keyboard.
    msg = update.effective_message
    if msg:
        await msg.reply_text(text, reply_markup=markup)


async def vynexa_discount_handler(update, context):
    try:
        msg = update.effective_message
        code = str(msg.text or "").strip()

        if not code:
            return

        order = context.user_data.get("order")
        if not order:
            context.user_data.pop("waiting_discount", None)
            context.user_data.pop("waiting_discount_code", None)
            return await msg.reply_text("❌ سفارش فعالی پیدا نشد.")

        users = load_users()
        uid = str(update.effective_user.id)
        user = users.setdefault(uid, {})

        # لیست تخفیف‌های اعمال‌شده روی همین سفارش
        discounts = order.setdefault("discounts", [])

        used_codes = {
            str(x.get("code", "")).strip().lower()
            for x in discounts
            if isinstance(x, dict)
        }

        # -------------------------------------------------
        # تشخیص نوع سرویس
        # -------------------------------------------------
        service_text = " ".join(
            str(order.get(k, ""))
            for k in (
                "service",
                "service_name",
                "vpn_type",
                "tier",
                "v2ray_tier",
                "plan",
                "category",
                "product",
                "name",
                "title",
                "type",
            )
        ).lower()

        if (
            "wireguard" in service_text
            or "wire guard" in service_text
        ):
            current_tier = "wireguard"
        elif "openvpn" in service_text or "open vpn" in service_text:
            current_tier = "openvpn"
        elif "pro" in service_text or "پرو" in service_text:
            current_tier = "pro"
        elif "normal" in service_text or "عادی" in service_text:
            current_tier = "normal"
        elif "economic" in service_text or "اقتصادی" in service_text:
            current_tier = "economic"
        else:
            current_tier = ""

        tier_names = {
            "pro": "V2Ray Pro",
            "normal": "V2Ray عادی",
            "economic": "V2Ray اقتصادی",
            "openvpn": "OpenVPN",
            "wireguard": "WireGuard",
        }

        # =================================================
        # 🎲 کد گردونه
        # =================================================
        dice_rewards = user.get("dice_discount_rewards", [])
        if not isinstance(dice_rewards, list):
            dice_rewards = []

        dice_reward = next(
            (
                r for r in dice_rewards
                if isinstance(r, dict)
                and str(r.get("code", "")).strip().upper() == code.upper()
                and not r.get("used", False)
            ),
            None
        )

        if dice_reward:
            reward_tier = str(dice_reward.get("tier", "")).strip().lower()
            percent = 10

            if reward_tier != current_tier:
                context.user_data.pop("waiting_discount", None)
                context.user_data.pop("waiting_discount_code", None)
                return await msg.reply_text(
                    f"❌ این کد فقط برای "
                    f"{tier_names.get(reward_tier, 'نوع سرویس مشخص')} است."
                )

            if code.lower() in used_codes:
                context.user_data.pop("waiting_discount", None)
                context.user_data.pop("waiting_discount_code", None)
                return await msg.reply_text(
                    "❌ این کد قبلاً روی این سفارش اعمال شده است."
                )

            old_price = int(order.get("price", 0) or 0)
            if old_price <= 0:
                return await msg.reply_text("❌ قیمت سفارش مشخص نیست.")

            discount = old_price * percent // 100
            new_price = old_price - discount

            discounts.append({
                "code": code,
                "percent": percent,
                "amount": discount,
                "type": "dice",
                "tier": reward_tier,
                "applied_at": datetime.now().isoformat(),
            })

            order["price"] = new_price
            order["discount_code"] = " + ".join(
                str(x.get("code"))
                for x in discounts
                if x.get("code")
            )

            dice_reward["used"] = True
            dice_reward["used_at"] = datetime.now().isoformat()

            save_users(users)
            context.user_data["order"] = order
            context.user_data.pop("waiting_discount", None)
            context.user_data.pop("waiting_discount_code", None)

            return await _return_to_payment_menu(
                update, context, order,
                "✅ کد گردونه اعمال شد: " + code + f" (تخفیف {percent}٪)"
                + f"\n💰 مبلغ قبل: {money(old_price)} | مبلغ نهایی: {money(new_price)}"
            )

        # =================================================
        # 💙 کد اصلی Vynexa
        # =================================================
        if code.lower() == "vynexa":

            if "vynexa" in used_codes:
                context.user_data.pop("waiting_discount", None)
                context.user_data.pop("waiting_discount_code", None)
                return await msg.reply_text(
                    "❌ کد Vynexa قبلاً روی این سفارش اعمال شده است."
                )

            old_price = int(order.get("price", 0) or 0)
            if old_price <= 0:
                return await msg.reply_text("❌ قیمت سفارش مشخص نیست.")

            discount = old_price * 10 // 100
            new_price = old_price - discount

            discounts.append({
                "code": "Vynexa",
                "percent": 10,
                "amount": discount,
                "type": "main",
                "tier": current_tier,
                "applied_at": datetime.now().isoformat(),
            })

            order["price"] = new_price
            order["discount_code"] = " + ".join(
                str(x.get("code"))
                for x in discounts
                if x.get("code")
            )

            context.user_data["order"] = order
            context.user_data.pop("waiting_discount", None)
            context.user_data.pop("waiting_discount_code", None)

            return await _return_to_payment_menu(
                update, context, order,
                "✅ کد تخفیف Vynexa اعمال شد؛ ۱۰٪ تخفیف گرفتید."
                + f"\n💰 مبلغ قبل: {money(old_price)} | مبلغ نهایی: {money(new_price)}"
            )

        context.user_data.pop("waiting_discount", None)
        context.user_data.pop("waiting_discount_code", None)
        return await _return_to_payment_menu(
            update, context, order, "❌ کد تخفیف نامعتبر است؛ دوباره بررسی کن."
        )

    except Exception as e:
        print("DISCOUNT ERROR:", repr(e))
        context.user_data.pop("waiting_discount", None)
        context.user_data.pop("waiting_discount_code", None)
        return await msg.reply_text(
            "❌ خطایی هنگام بررسی کد تخفیف رخ داد."
        )

async def payment_menu(update, context):
    o = context.user_data.get('order')
    if not o: return
    await update.message.reply_text(
        order_summary(o) + '\n\nروش پرداخت را انتخاب کن:',
        reply_markup=kb([
            ['💳 کارت به کارت'],
            ['💰 استفاده از کیف پول'],
            ['🎟 کد تخفیف دارم'],
            ['🔙 برگشت']
        ])
    )


async def show_card(update, context):
    o = context.user_data.get('order')
    if not o: return
    card = load_config().get('card_number', 'شماره کارت در config.json تنظیم نشده')
    owner = load_config().get('card_name', 'نام صاحب کارت')
    context.user_data['waiting_receipt'] = True
    await update.message.reply_text(
        '💳 کارت به کارت\n\n'
        f'💰 مبلغ: {money(o.get("price",0))}\n'
        f'💳 شماره کارت: {card}\n'
        f'👤 به نام: {owner}\n\n'
        'بعد از پرداخت، عکس رسید را همینجا ارسال کن.'
    )


async def use_wallet(update, context):
    o = context.user_data.get("order")
    uid = update.effective_user.id

    if not o:
        return

    b = wallet_balance(uid)
    price = int(o.get("price", 0) or 0)

    # مبلغی که قبلاً از کیف پول برای همین سفارش پرداخت شده
    wallet_paid = int(o.get("wallet_paid", 0) or 0)
    remaining = max(0, price - wallet_paid)

    if b <= 0:
        return await update.message.reply_text(
            f"❌ موجودی کیف پول صفر است.\n\n"
            f"💰 مبلغ باقی‌مانده سفارش: {money(remaining)}",
            reply_markup=kb([
                ['➕ شارژ کیف پول'],
                ['💳 پرداخت با کارت‌به‌کارت'],
                ['🔙 برگشت']
            ])
        )

    # تمام مبلغ باقی‌مانده با کیف پول
    if b >= remaining:
        users = load_users()
        users[str(uid)]["wallet"] = b - remaining
        save_users(users)

        o["wallet_paid"] = wallet_paid + remaining
        o["status"] = "paid"
        o["payment"] = "wallet"
        o["paid_at"] = datetime.now().isoformat()

        orders = load_orders()
        orders[o["id"]] = o
        save_orders(orders)

        context.user_data.pop("order", None)

        await update.message.reply_text(
            "✅ پرداخت از کیف پول با موفقیت انجام شد.\n\n"
            "⏳ سفارش برای آماده‌سازی کانفیگ ارسال شد.",
            reply_markup=home(uid)
        )

        return await notify_admin_payment(context, o, None)

    # فقط بخشی از سفارش با کیف پول پرداخت می‌شود
    paid_now = b
    users = load_users()
    users[str(uid)]["wallet"] = 0
    save_users(users)

    o["wallet_paid"] = wallet_paid + paid_now
    o["wallet_payment"] = True
    o["remaining_price"] = max(0, price - o["wallet_paid"])

    orders = load_orders()
    orders[o["id"]] = o
    save_orders(orders)

    remaining = o["remaining_price"]

    return await update.message.reply_text(
        "💰 پرداخت از کیف پول انجام شد.\n\n"
        f"✅ مبلغ کسرشده: {money(paid_now)}\n"
        f"💵 مبلغ باقی‌مانده: {money(remaining)}\n\n"
        "یکی از روش‌های زیر را انتخاب کن:",
        reply_markup=kb([
            ['💳 پرداخت باقی‌مانده با کارت‌به‌کارت'],
            ['➕ شارژ کیف پول و پرداخت باقی‌مانده'],
            ['🔙 برگشت']
        ])
    )


async def notify_admin_payment(context, o, photo_id=None):
    aid = admin_id()
    if not aid: return
    cap = '💳 رسید پرداخت جدید\n\n' + order_summary(o)
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton('✅ تأیید پرداخت', callback_data=f'payok:{o["id"]}'),
        InlineKeyboardButton('❌ رد پرداخت', callback_data=f'payno:{o["id"]}')
    ]])
    try:
        if photo_id:
            await context.bot.send_photo(aid, photo=photo_id, caption=cap, reply_markup=markup)
        else:
            await context.bot.send_message(aid, cap, reply_markup=markup)
    except Exception as e:
        print('ADMIN PAYMENT ERROR:', repr(e))


async def photo_handler(update, context):
    if (
        update.effective_user
        and is_admin(update.effective_user.id)
        and context.user_data.get("channel_send")
    ):
        return await do_send_to_channel(update, context)

    uid = update.effective_user.id; photo = update.message.photo[-1].file_id
    if context.user_data.get('wallet_receipt_order'):
        oid = context.user_data.pop('wallet_receipt_order'); orders = load_orders(); o = orders.get(oid)
        if not o: return await update.message.reply_text('❌ درخواست شارژ پیدا نشد.')
        o['receipt_photo'] = photo; orders[oid] = o; save_orders(orders)
        await update.message.reply_text('✅ رسید شارژ کیف پول دریافت شد. منتظر بررسی باشید.')
        cap = '💰 درخواست شارژ کیف پول\n\n👤 کاربر: ' + str(uid) + '\n💵 مبلغ: ' + money(o['amount'])
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('✅ تأیید شارژ', callback_data=f'walletok:{oid}'), InlineKeyboardButton('❌ رد شارژ', callback_data=f'walletno:{oid}')]])
        return await context.bot.send_photo(admin_id(), photo=photo, caption=cap, reply_markup=markup)
    if context.user_data.get('waiting_receipt') and context.user_data.get('order'):
        context.user_data.pop('waiting_receipt', None)
        o = context.user_data['order']; o['status'] = 'pending_payment'; o['receipt_photo'] = photo
        orders = load_orders(); orders[o['id']] = o; save_orders(orders)
        await update.message.reply_text('✅ رسید دریافت شد.\n⏳ منتظر بررسی پرداخت باشید.')
        return await notify_admin_payment(context, o, photo)
    if is_admin(uid) and context.user_data.get('delivery_order'):
        return await save_delivery_item(update, context, {'type':'photo','value':photo})


async def document_handler(update, context):
    if is_admin(update.effective_user.id) and context.user_data.get('delivery_order'):
        return await save_delivery_item(update, context, {'type':'document','value':update.message.document.file_id})


async def save_delivery_item(update, context, item):
    oid = context.user_data.get('delivery_order'); orders = load_orders(); o = orders.get(oid)
    if not o: return await update.message.reply_text('❌ سفارش پیدا نشد.')
    o.setdefault('delivery', []).append(item); orders[oid] = o; save_orders(orders)
    await update.message.reply_text('✅ ذخیره شد. منتظر مورد بعدی هستم.')



# ===== VYNEXA V2ROUTE QR =====
def find_v2route_qr(data):
    """Find QR image/file/url returned by V2Route API."""
    if not isinstance(data, dict):
        return None

    keys = (
        "qr_code",
        "qrcode",
        "qr",
        "qr_url",
        "qr_code_url",
        "qrcode_url",
        "qr_image",
        "qr_image_url",
        "qrCode",
        "qrCodeUrl",
    )

    def scan(obj):
        if isinstance(obj, dict):
            for k in keys:
                v = obj.get(k)
                if v:
                    return v
            for v in obj.values():
                r = scan(v)
                if r:
                    return r

        elif isinstance(obj, list):
            for v in obj:
                r = scan(v)
                if r:
                    return r

        return None

    return scan(data)


async def send_vynexa_v2route_qr(context, uid, qr):
    """Send V2Route's own QR. No Pillow / QR generation."""
    if not qr:
        print("V2ROUTE QR: not found in API response")
        return False

    try:
        # URL
        if isinstance(qr, str) and qr.startswith(("http://", "https://")):
            await context.bot.send_photo(
                chat_id=uid,
                photo=qr,
                caption="@VynexaVPN_bot"
            )
            return True

        # Telegram file_id
        if isinstance(qr, str):
            await context.bot.send_photo(
                chat_id=uid,
                photo=qr,
                caption="@VynexaVPN_bot"
            )
            return True

        return False

    except Exception as e:
        print("VYNEXA QR SEND ERROR:", repr(e))
        return False



# ===== VYNEXA QR SENDER =====
async def send_vynexa_qr(context, uid, url):
    if not url:
        return False
    import os, tempfile
    from PIL import Image, ImageDraw, ImageFont
    import qrcode

    path = None
    try:
        W, H = 900, 1120
        img = Image.new("RGB", (W, H), "#0758D8")
        px = img.load()
        top = (4, 74, 190)
        bottom = (14, 190, 255)
        for y in range(H):
            t = y / (H - 1)
            c = tuple(int(top[i] * (1-t) + bottom[i] * t) for i in range(3))
            for x in range(W):
                px[x, y] = c

        draw = ImageDraw.Draw(img)
        # Decorative blue bubbles
        for x, y, r, color in [
            (70, 100, 48, "#39C6FF"), (820, 150, 68, "#2B9BFF"),
            (90, 850, 75, "#1675E8"), (820, 900, 52, "#42D5FF"),
            (760, 390, 24, "#80E6FF"), (130, 410, 20, "#80E6FF"),
            (760, 1030, 30, "#0871D9"), (210, 1030, 18, "#5DDCFF")
        ]:
            draw.ellipse((x-r, y-r, x+r, y+r), fill=color)

        def font(size, bold=False):
            candidates = (
                ["/system/fonts/Roboto-Bold.ttf", "/system/fonts/NotoSans-Bold.ttf"]
                if bold else
                ["/system/fonts/Roboto-Regular.ttf", "/system/fonts/NotoSans-Regular.ttf"]
            )
            for f in candidates:
                if os.path.exists(f):
                    try:
                        return ImageFont.truetype(f, size)
                    except Exception:
                        pass
            return ImageFont.load_default()

        title_font = font(58, True)
        subtitle_font = font(30)
        id_font = font(38, True)
        small_font = font(25)

        draw.text((W//2, 80), "VynexaVPN", font=title_font,
                  fill="white", anchor="mt", stroke_width=1)
        draw.text((W//2, 160), "SCAN TO CONNECT", font=subtitle_font,
                  fill="#E8F7FF", anchor="mt")

        # White rounded card
        card = (105, 245, 795, 890)
        draw.rounded_rectangle(card, radius=48, fill="#FFFFFF")
        qr = qrcode.QRCode(
            version=None, error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=12, border=3
        )
        qr.add_data(str(url))
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#061B3A", back_color="white").convert("RGB")
        qr_img.thumbnail((570, 570))
        qx = (W - qr_img.width) // 2
        qy = 285 + (560 - qr_img.height) // 2
        img.paste(qr_img, (qx, qy))

        draw.text((W//2, 925), "@VynexaVPN_bot", font=id_font,
                  fill="white", anchor="mt")
        draw.text((W//2, 990), "دنیای بدون مرز", font=subtitle_font,
                  fill="white", anchor="mt")
        draw.text((W//2, 1060), "VynexaVPN • Official Bot", font=small_font,
                  fill="#E8F7FF", anchor="mt")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        img.save(path, "PNG")
        with open(path, "rb") as photo:
            await context.bot.send_photo(
                chat_id=uid, photo=photo,
                caption="💙 QR اختصاصی VynexaVPN\n@VynexaVPN_bot"
            )
        return True
    except Exception as e:
        print("QR POSTER ERROR:", repr(e))
        return False
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass





# ===== VYNEXA LIVE INFO =====

def _fmt_gb(v):
    try:
        return f"{float(v):.2f} GB"
    except Exception:
        return str(v)


def _remaining_days(expire):
    try:
        from datetime import datetime
        if not expire:
            return None
        d = datetime.fromtimestamp(int(expire))
        return max(0, (d - datetime.now()).days)
    except Exception:
        return None


async def v2route_live_info(o):
    import httpx

    url = o.get("subscription_url")

    if not url:
        for x in o.get("delivery", []):
            if x.get("type") == "text":
                v = str(x.get("value", ""))
                if v.startswith(("http://", "https://")):
                    url = v
                    break

    if not url:
        return None, "لینک اشتراک برای بررسی زنده پیدا نشد."

    try:
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True
        ) as client:

            r = await client.get(url)

        header = (
            r.headers.get("subscription-userinfo")
            or r.headers.get("Subscription-Userinfo")
        )

        if not header:
            return None, "اطلاعات زنده از Subscription دریافت نشد."

        vals = {}

        for part in header.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                vals[k.strip().lower()] = v.strip()

        total = int(vals.get("total", "0") or 0)
        upload = int(vals.get("upload", "0") or 0)
        download = int(vals.get("download", "0") or 0)
        used = upload + download

        remaining = max(0, total - used) if total else 0

        expire = int(vals.get("expire", "0") or 0)

        return {
            "total": total,
            "used": used,
            "remaining": remaining,
            "expire": expire
        }, None

    except Exception as e:
        # DNS errors can repeat for every saved service; log each hostname once.
        try:
            from urllib.parse import urlsplit
            host = urlsplit(str(url)).hostname or 'unknown-host'
        except Exception:
            host = 'unknown-host'
        seen = globals().setdefault('_VYNEXA_LIVE_INFO_ERROR_HOSTS', set())
        if host not in seen:
            seen.add(host)
            print("LIVE INFO ERROR (logged once for host):", host, repr(e)[:180])
        return None, "اطلاعات زنده فعلاً در دسترس نیست؛ اتصال لینک اشتراک برقرار نشد."


def live_info_text(o, info):

    if not info:
        return "⚠️ اطلاعات زنده در دسترس نیست."

    days = _remaining_days(info.get("expire"))

    lines = [
        "📊 اطلاعات زنده سرویس",
        "",
        "🌐 سرویس: " + str(o.get("service", "V2Ray")),
        "📦 حجم کل: " + _fmt_gb(info.get("total", 0) / (1024**3)),
        "📉 مصرف‌شده: " + _fmt_gb(info.get("used", 0) / (1024**3)),
        "📦 حجم باقی‌مانده: " + _fmt_gb(info.get("remaining", 0) / (1024**3)),
    ]

    if days is not None:
        lines.append("⏳ روز باقی‌مانده: " + str(days) + " روز")

    return "\n".join(lines)




# ===== VYNEXA QR =====

async def send_vynexa_qr(context, uid, url):
    if not url:
        return False
    import qrcode, tempfile, os
    path = None
    try:
        img = qrcode.make(str(url))
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        img.save(path)
        with open(path, "rb") as photo:
            await context.bot.send_photo(
                chat_id=uid, photo=photo,
                caption="🔳 QR کد لینک اتصال | @VynexaVPN_bot"
            )
        return True
    except Exception as e:
        print("QR ERROR:", repr(e))
        return False
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass




# ===== V2ROUTE API =====
V2ROUTE_TOKEN = 'rsk_kRvG3w4q0gRYbVAmKcMmgtSLj5ZbdeyQ1iQa632u'
V2ROUTE_BASE = "https://v2route.com/api/reseller"


async def v2route_create_service(o):
    import httpx
    import re

    tier_map = {"اقتصادی": "economy", "عادی": "standard"}
    tier = tier_map.get(str(o.get("v2ray_tier", "")))

    if not tier or str(o.get("duration", "")) != "1 ماهه":
        return None, "این سفارش برای ساخت خودکار V2Route نیست."

    if V2ROUTE_TOKEN == "PASTE_V2ROUTE_TOKEN_HERE":
        return None, "V2Route Token وارد نشده است."

    m = re.search(r"(\d+(?:\.\d+)?)\s*GB", str(o.get("volume", "")), re.I)

    if not m:
        return None, "حجم سفارش قابل تشخیص نیست."

    payload = {
        "name": "Vynexa-" + str(o["id"]),
        "tier": tier,
        "gb": (int(float(m.group(1))) if float(m.group(1)).is_integer() else float(m.group(1))),
    }

    headers = {
        "Authorization": "Bearer " + V2ROUTE_TOKEN,
        "Content-Type": "application/json",
        "Idempotency-Key": str(o["id"]),
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                V2ROUTE_BASE + "/clients",
                headers=headers,
                json=payload
            )

        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}

        print("V2ROUTE CREATE:", r.status_code, data)

        if not r.is_success:
            return None, "V2Route HTTP " + str(r.status_code) + ": " + str(data)

        client_data = data.get("client", {}) if isinstance(data, dict) else {}

        url = (
            data.get("subscription_url")
            or data.get("subscriptionUrl")
            or data.get("sub_url")
            or client_data.get("subscription_url")
            or client_data.get("subscriptionUrl")
            or client_data.get("sub_url")
        )

        if not url:
            return None, "لینک subscription در پاسخ API پیدا نشد: " + str(data)

        # لینک را مستقیماً داخل سفارش ذخیره کن
        o["subscription_url"] = str(url)

        # تلاش برای پیدا کردن QR از پاسخ API
        qr = None

        def find_qr(obj):
            if isinstance(obj, dict):
                names = (
                    "qr",
                    "qrcode",
                    "qr_code",
                    "qr_url",
                    "qrcode_url",
                    "qr_code_url",
                    "qr_image",
                    "qr_image_url",
                    "qrCode",
                    "qrCodeUrl",
                )

                for name in names:
                    value = obj.get(name)
                    if value:
                        return value

                for value in obj.values():
                    found = find_qr(value)
                    if found:
                        return found

            elif isinstance(obj, list):
                for value in obj:
                    found = find_qr(value)
                    if found:
                        return found

            return None

        qr = find_qr(data)

        if qr:
            o["v2route_qr"] = qr
            print("V2ROUTE QR FOUND:", qr)
        else:
            print("V2ROUTE QR: not found in API response")

        return str(url), None

    except Exception as e:
        print("V2ROUTE ERROR:", repr(e))
        return None, repr(e)


async def admin_confirm(update, context, ok):
    q = update.callback_query
    await q.answer()
    oid = q.data.split(':', 1)[1]
    orders = load_orders()
    o = orders.get(oid)
    if not o:
        return await q.answer('❌ سفارش پیدا نشد.', show_alert=True)
    uid = int(o['user_id'])
    if not ok:
        o['status'] = 'rejected'
        orders[oid] = o
        save_orders(orders)
        try:
            await q.edit_message_caption(caption='❌ پرداخت رد شد.\n\n' + order_summary(o))
        except Exception:
            try: await q.edit_message_text('❌ پرداخت رد شد.\n\n' + order_summary(o))
            except Exception: pass
        await context.bot.send_message(uid, '❌ پرداخت شما تأیید نشد.')
        return

    o['status'] = 'paid'
    o['paid_at'] = datetime.now().isoformat()
    orders[oid] = o
    save_orders(orders)
    try:
        await q.edit_message_caption(caption='✅ پرداخت تأیید شد.\n\n' + order_summary(o))
    except Exception:
        try: await q.edit_message_text('✅ پرداخت تأیید شد.\n\n' + order_summary(o))
        except Exception: pass

    if o.get('type') == 'renewal':
        await context.bot.send_message(uid, '⏳ پرداخت تمدید تأیید شد.\n🔄 در حال تمدید همان اشتراک...')
        ok_renew, result = await v2route_renew_service(o)
        if ok_renew:
            original_id = str(o.get('original_order_id', ''))
            original = orders.get(original_id, {})
            original['renewed_at'] = datetime.now().isoformat()
            original['last_renewal_order_id'] = oid
            original['renewal_count'] = int(original.get('renewal_count', 0)) + 1
            original['expiry_notice_state'] = {}
            original['status'] = 'delivered'
            orders[original_id] = original
            o['status'] = 'renewed'; o['renewed_at'] = datetime.now().isoformat()
            orders[oid] = o; save_orders(orders)
            await context.bot.send_message(
                uid,
                '🎉 تمدید سرویس با موفقیت انجام شد!\n\n'
                '💙 اشتراک قبلی شما بدون تغییر تمدید شد و لینک جدیدی ساخته نشد.\n\n'
                '━━━━━━━━━━━━━━━━━━\n'
                '📦 مشخصات تمدید\n'
                '━━━━━━━━━━━━━━━━━━\n'
                f'🌐 سرویس: {original.get("service", "V2Ray")}\n'
                f'📊 حجم: {original.get("volume", "-")}\n'
                f'⏳ مدت تمدید: {original.get("duration", "-")}\n'
                '━━━━━━━━━━━━━━━━━━\n\n'
                '✅ سرویس شما در پنل تمدید شد.\n'
                '🔗 همان لینک اشتراک قبلی را استفاده کنید.\n\n'
                '❤️ ممنون که Vynexa-VPN را انتخاب کردید.'
            , reply_markup=home(uid))
            return
        o['status'] = 'renew_api_failed'; o['api_error'] = result
        orders[oid] = o; save_orders(orders)
        await context.bot.send_message(uid, '⚠️ پرداخت تمدید تأیید شد، اما تمدید در پنل با خطا مواجه شد.\n⏳ مدیر در حال بررسی است.')
        try: await context.bot.send_message(admin_id(), '❌ خطای تمدید V2Route\n🆔 سفارش: ' + oid + '\n' + str(result))
        except Exception: pass
        return

    is_auto_v2 = (
        str(o.get('service', '')).lower() == 'v2ray' and
        str(o.get('duration', '')) in ('1 ماهه', '3 ماهه') and
        str(o.get('v2ray_tier', '')) in ('اقتصادی', 'عادی')
    )
    if is_auto_v2:
        await context.bot.send_message(uid, '⏳ پرداخت تأیید شد.\n📦 در حال ساخت سرویس شما...')
        sub_url, err = await v2route_create_service(o)
        if sub_url:
            o['status'] = 'delivered'
            o['subscription_url'] = sub_url
            o['delivered_at'] = datetime.now().isoformat()
            orders[oid] = o
            save_orders(orders)
            duration = str(o.get('duration', '-'))
            volume = str(o.get('volume', '-'))
            success_text = (
                '🎉 کانفیگ شما با موفقیت دریافت شد!\n\n'
                '💙 ممنون که Vynexa-VPN را انتخاب کردید.\n'
                'امیدواریم این سرویس برای شما تجربه‌ای سریع، پایدار و بدون دردسر فراهم کند.\n\n'
                '━━━━━━━━━━━━━━━━━━\n'
                '📦 مشخصات سرویس شما\n'
                '━━━━━━━━━━━━━━━━━━\n'
                '🌐 سرویس: V2Ray\n'
                '📅 مدت: ' + duration + '\n'
                '📊 حجم: ' + volume + '\n'
                '━━━━━━━━━━━━━━━━━━\n\n'
                '🔗 لینک اتصال شما:\n' + sub_url + '\n\n'
                '⚠️ این لینک اختصاصی است؛ آن را در اختیار دیگران قرار ندهید و برای استفاده‌های بعدی نگه دارید.\n\n'
                '📚 برای آموزش استفاده از یکی از دکمه‌های زیر استفاده کنید.\n\n'
                '✨ امیدواریم از سرویس Vynexa-VPN لذت ببرید ❤️'
            )
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton('⭐ آموزش استفاده از V2Ray (پیشنهادی)', url='https://sv5.downloadyarbot.ir/IDM/vynexa-vpn-guide-1.html')],
                [InlineKeyboardButton('⚡ آموزش V2Box / Happ / V2RayTun', url='https://sv1.downloadyarbot.ir/IDM/vynexa-vpn-guides-all.html')],
                [InlineKeyboardButton('🍎 آموزش استفاده در آیفون', url='https://sv5.downloadyarbot.ir/IDM/vynexa-vpn-iphone-guides.html')]
            ])
            await context.bot.send_message(uid, success_text, reply_markup=buttons)
            await record_successful_referral(context, o)
            await send_vynexa_v2route_qr(
                context,
                uid,
                o.get("v2route_qr")
            )
            return
        o['status'] = 'paid_api_failed'
        o['api_error'] = err or 'unknown error'
        orders[oid] = o
        save_orders(orders)
        await context.bot.send_message(uid, '⚠️ پرداخت تأیید شد، اما ساخت خودکار سرویس با خطا مواجه شد.\n⏳ مدیر در حال بررسی است.')
        try: await context.bot.send_message(admin_id(), '❌ خطای V2Route\n🆔 سفارش: ' + oid + '\n' + str(err))
        except Exception: pass
        return

    await context.bot.send_message(uid, '✅ پرداخت شما تأیید شد.\n\n📥 اطلاعات سرویس پس از آماده‌سازی ارسال می‌شود.')
    context.user_data['delivery_order'] = oid
    try:
        await context.bot.send_message(admin_id(), '📥 اطلاعات سرویس را برای این سفارش ارسال کن:\n\n🆔 سفارش: ' + oid, reply_markup=admin_panel())
    except Exception as e:
        print('ADMIN DELIVERY ERROR:', repr(e))

async def send_saved_config(context, oid):
    import re
    orders = load_orders()
    o = orders.get(oid)
    if not o:
        return False
    vals = o.get("delivery", [])
    if not vals:
        return False
    uid = int(o["user_id"])

    await context.bot.send_message(
        uid,
        "🎉 کانفیگ شما با موفقیت ارسال شد!\n\n"
        "💙 از خرید شما از VynexaVPN سپاسگزاریم."
    )

    for item in vals:
        kind = item.get("type", "text")
        value = item.get("value", "")
        if kind == "photo":
            await context.bot.send_photo(chat_id=uid, photo=value)
        elif kind == "document":
            await context.bot.send_document(chat_id=uid, document=value)
        else:
            text = str(value)
            await context.bot.send_message(chat_id=uid, text=text)
            match = re.search(r"https?://[^\s<>]+", text)
            if match:
                url = match.group(0).rstrip(".,،؛)")
                await send_vynexa_qr(context, uid, url)

    o["status"] = "delivered"
    o["delivered_at"] = datetime.now().isoformat()
    orders[oid] = o
    save_orders(orders)
    await record_successful_referral(context, o)
    return True



async def send_config_menu(update, context):
    if not is_admin(update.effective_user.id): return
    orders = load_orders(); arr = [(oid,o) for oid,o in orders.items() if o.get('status') == 'paid' and o.get('delivery')]
    if not arr: return await update.message.reply_text('❌ سفارشی با اطلاعات آماده ارسال وجود ندارد.')
    buttons = []
    for oid,o in arr[-30:]:
        buttons.append([InlineKeyboardButton(f'{o.get("service","-")} — {oid}', callback_data=f'sendcfg:{oid}')])
    await update.message.reply_text('🚀 سفارش موردنظر را انتخاب کن:', reply_markup=InlineKeyboardMarkup(buttons))


async def send_to_channel(update, context):
    if not is_admin(update.effective_user.id):
        return

    context.user_data['channel_send'] = True
    await update.message.reply_text(
        '📢 متن پیام کانال را ارسال کن:'
    )


async def do_send_to_channel(update, context):
    if not update.effective_user or not is_admin(update.effective_user.id):
        return

    msg = update.effective_message
    if not msg:
        return

    try:
        if msg.photo:
            caption = msg.caption or ""
            if len(caption) > 1024:
                await context.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=msg.photo[-1].file_id,
                    reply_markup=vynexa_channel_buttons()
                )
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=caption,
                    reply_markup=vynexa_channel_buttons()
                )
            else:
                await context.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=msg.photo[-1].file_id,
                    caption=caption or None,
                    reply_markup=vynexa_channel_buttons()
                )
        elif msg.text:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=msg.text,
                reply_markup=vynexa_channel_buttons()
            )
        else:
            await msg.reply_text("❌ لطفاً متن یا عکس ارسال کن.")
            return

        context.user_data.pop("channel_send", None)
        await msg.reply_text("✅ پیام در کانال ارسال شد.")

    except Exception as e:
        await msg.reply_text(
            "❌ ارسال پیام ناموفق بود:\n" + str(e)[:500]
        )

async def join_request_handler(update, context):
    req = update.chat_join_request
    if not req:
        return

    if int(req.chat.id) != int(JOIN_CHANNEL_ID):
        return

    user = req.from_user
    name = user.full_name or "بدون نام"
    username = "@" + user.username if user.username else "ندارد"

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "تایید عضویت",
                callback_data="approve_join:" + str(req.chat.id) + ":" + str(user.id)
            ),
            InlineKeyboardButton(
                "رد درخواست",
                callback_data="decline_join:" + str(req.chat.id) + ":" + str(user.id)
            )
        ]
    ])

    text = (
        "🔔 درخواست عضویت جدید\n\n"
        + "👤 نام: " + name + "\n"
        + "🆔 آیدی: " + str(user.id) + "\n"
        + "🔗 یوزرنیم: " + username + "\n\n"
        + "یکی از گزینه‌ها را انتخاب کنید."
    )

    try:
        await context.bot.send_message(
            chat_id=8269636855,
            text=text,
            reply_markup=keyboard
        )
        print("JOIN REQUEST SENT TO ADMIN:", user.id)

    except Exception as e:
        print("JOIN REQUEST PRIVATE MESSAGE ERROR:", repr(e))


async def join_approval_callback(update, context):
    query = update.callback_query

    if not query:
        return

    data = query.data or ""

    if not (
        data.startswith("approve_join:")
        or data.startswith("decline_join:")
    ):
        return

    if query.from_user.id != 8269636855 or not is_admin(query.from_user.id):
        await query.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )
        return

    try:
        action, chat_id, user_id = data.split(":")
        chat_id = int(chat_id)
        user_id = int(user_id)

        if action == "approve_join":
            await context.bot.approve_chat_join_request(
                chat_id=chat_id,
                user_id=user_id
            )

            await query.answer("✅ عضویت تأیید شد")
            await query.edit_message_text(
                query.message.text + "\n\n✅ تأیید شد"
            )

        elif action == "decline_join":
            await context.bot.decline_chat_join_request(
                chat_id=chat_id,
                user_id=user_id
            )

            await query.answer("❌ درخواست رد شد")
            await query.edit_message_text(
                query.message.text + "\n\n❌ رد شد"
            )

    except Exception as e:
        print("JOIN APPROVAL ERROR:", repr(e))
        await query.answer(
            "❌ خطا در انجام عملیات",
            show_alert=True
        )



async def vynexa_channel_member_update(update, context):
    try:
        chat = update.effective_chat
        change = update.chat_member
        if not chat or (chat.username or "").lower() != "vynexavpn":
            return

        old_status = change.old_chat_member.status
        new_status = change.new_chat_member.status
        if old_status not in ("member", "administrator", "creator", "restricted"):
            return
        if new_status != "left":
            return

        user = change.new_chat_member.user
        if user.is_bot:
            return

        message = (
            "💙 رفیق عزیز، دیدیم که از کانال وینکسا خارج شدی!\n\n"
            "امیدواریم تجربه خوبی کنارمون داشته باشی. اگر مشکلی پیش اومده "
            "یا پیشنهادی داری، خوشحال می‌شیم باهامون در میون بذاری. ✨\n\n"
            "هر وقت خواستی برگردی، درهای وینکسا به روت بازه! 🌐💙\n\n"
            "📢 کانال: @VynexaVPN\n"
            "🤖 ربات: @VynexaVPN_bot\n\n"
            "VynexaVPN | دنیای بدون مرز💙"
        )
        await context.bot.send_message(chat_id=user.id, text=message)
    except Exception as e:
        print("CHANNEL LEAVE MESSAGE ERROR:", repr(e))


async def announce(update, context):
    if not is_admin(update.effective_user.id): return
    context.user_data['announce'] = True
    await update.message.reply_text('📢 متن اطلاعیه را ارسال کن:')


async def do_announce(update, context):
    context.user_data.pop('announce', None)
    text = update.message.text
    users = set(load_users().keys()) | {str(o.get('user_id')) for o in load_orders().values() if o.get('user_id')}
    sem = asyncio.Semaphore(20)
    async def send(uid):
        async with sem:
            try:
                await context.bot.send_message(int(uid), text); return 1
            except Exception: return 0
    sent = sum(await asyncio.gather(*(send(u) for u in users if str(u).isdigit()))) if users else 0
    await update.message.reply_text(f'✅ اطلاعیه برای {sent} نفر ارسال شد.', reply_markup=home(update.effective_user.id))


async def toggle_bot(update, context):
    if not is_admin(update.effective_user.id): return
    c=load_config(); c['bot_enabled']=not c.get('bot_enabled',True); save_config(c)
    await _vynexa_broadcast_toggle(context.bot, c['bot_enabled'])
    await update.message.reply_text('🟢 ربات روشن شد.' if c['bot_enabled'] else '🔴 ربات خاموش شد.', reply_markup=home(update.effective_user.id))


async def manage_vpn(update, context):
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text('⚙️ مدیریت VPN', reply_markup=kb([['✏️ ویرایش VPN'],['➕ افزودن VPN'],['🗑 حذف VPN'],['🔙 برگشت']]))


async def add_vpn_start(update, context):
    context.user_data.clear(); context.user_data['vpn_add'] = {'step':'name'}
    await update.message.reply_text('🌐 اسم VPN را وارد کن:')


async def edit_vpn_start(update, context):
    prices=load_config().get('prices',{}); rows=[[str(k)] for k,v in prices.items() if isinstance(v,dict)]
    rows.append(['🔙 برگشت']); context.user_data['vpn_edit_select']=True
    await update.message.reply_text('✏️ VPN موردنظر را انتخاب کن:', reply_markup=kb(rows))


async def delete_vpn_start(update, context):
    prices=load_config().get('prices',{}); rows=[[str(k)] for k,v in prices.items() if isinstance(v,dict)]
    rows.append(['🔙 برگشت']); context.user_data['vpn_delete_select']=True
    await update.message.reply_text('🗑 VPN موردنظر را انتخاب کن:', reply_markup=kb(rows))


async def edit_field_menu(update, context, name):
    context.user_data['vpn_edit_name']=name
    await update.message.reply_text(f'✏️ «{name}»\nچه چیزی را ویرایش می‌کنی؟', reply_markup=kb([['📦 حجم'],['⏳ مدت'],['🚀 سرعت'],['💰 قیمت'],['✏️ نام'],['🔙 برگشت']]))


async def customer_services(update, context):
    orders=load_orders(); arr=list(orders.items())
    if not arr: return await update.message.reply_text('👥 سفارشی ثبت نشده است.')
    context.user_data['_menu_force_new_messages'] = 'first'
    try:
        await update.message.reply_text(f'👥 سرویس‌ها و سفارش‌های مشتری‌ها ({min(len(arr), 50)} مورد آخر):')
        for oid,o in arr[-50:]:
            await update.message.reply_text(order_summary(o)+f'\n\n📌 وضعیت: {o.get("status","-")}')
    finally:
        context.user_data.pop('_menu_force_new_messages', None)


async def approved_services(update, context):
    orders=load_orders(); arr=[(oid,o) for oid,o in orders.items() if o.get('status') in ('paid','delivered','confirmed')]
    if not arr: return await update.message.reply_text('📦 سرویس تأییدشده‌ای نیست.')
    context.user_data['_menu_force_new_messages'] = 'first'
    try:
        await update.message.reply_text(f'📦 سرویس‌های تأییدشده ({min(len(arr), 50)} مورد آخر):')
        for oid,o in arr[-50:]:
            await update.message.reply_text(order_summary(o), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('📥 ارسال اطلاعات دوباره',callback_data=f'resend:{oid}')]]))
    finally:
        context.user_data.pop('_menu_force_new_messages', None)


# ===== VYNEXA LOCAL AI =====
# موتور مکالمه محلی؛ بدون اینترنت و بدون API Key.
# بانک پاسخ با ترکیب الگوها بیش از ۱۰۰۰ پاسخ متفاوت تولید می‌کند.

import random
import re
import hashlib

_LOCAL_BANK = None


def _build_local_bank():
    global _LOCAL_BANK, _LOCAL_GOOD, _LOCAL_WARM, _LOCAL_GENERIC, _LOCAL_THANKS, _LOCAL_GOODBYE, _LOCAL_JOKES
    if _LOCAL_BANK is not None:
        return _LOCAL_BANK

    greetings = [
        "سلام رفیق 👋", "سلام 😄", "سلام سلام! 👋😊", "درود رفیق 🌹", "سلام، خوش اومدی 😎",
        "سلام داداش 👋", "سلام عزیز، چطوری؟ 😊", "سلام رفیق، در خدمتم ✌️", "سلام! بگو ببینم چه خبر 😄",
        "سلام و صد سلام 🌹", "سلاممم 👋😁", "سلام، من اینجام 😎", "درود بر تو 👋", "سلام رفیق جان 😊",
        "سلام! چه خوب که اومدی 👋", "سلام 😎 بگو ببینم چی شده", "سلام، گوشم با توئه 👂😄", "سلام رفیق ✌️",
        "سلام! آماده‌ام کمکت کنم 😊", "سلام، بریم ببینیم چه کاری داری 👋"
    ]
    warm = [
        "چطور می‌تونم کمکت کنم؟", "بگو ببینم چی لازم داری.", "چه کاری از دستم برمیاد؟",
        "هرچی هست بگو، باهم حلش می‌کنیم.", "بگو، در خدمتم.", "خب رفیق، چه خبر؟",
        "چی تو ذهنت داری؟", "بگو ببینم دنبال چی هستی.", "هر سوالی داری بپرس.", "من گوشم با توئه 😄",
        "بگو از کجا شروع کنیم.", "چه کمکی می‌خوای؟", "بریم سر اصل مطلب 😎", "بگو ببینم چه کاری داری.",
        "هرچی می‌خوای بگو، راهنماییت می‌کنم.", "آماده‌ام، بگو.", "خب، بزن بریم! 🚀", "چی شده رفیق؟",
        "من در خدمتم، بگو.", "بگو ببینم چطور می‌تونم کمکت کنم."
    ]
    good = [
        "مرسی رفیق، خوبم 😄", "خوبم، ممنون که پرسیدی 🌹", "عالی‌ام رفیق 😎", "خوبم و آماده‌ام کمکت کنم ✌️",
        "مرسی، رو به راهم 😄", "خوبم داداش، تو چطوری؟", "فعلاً همه‌چی مرتبه 😁", "خوبم، بگو ببینم تو چه خبر؟",
        "مرسی ازت، خوبم ❤️", "خوبم رفیق، در خدمتم.", "عالی، ممنون که پرسیدی 👋", "خوبم 😄 تو بگو چه خبر؟"
    ]
    thanks = [
        "خواهش می‌کنم رفیق ❤️", "قابلی نداشت 😄", "خواهش می‌کنم، انجام وظیفه‌ست.", "مرسی از لطفت 🌹",
        "دمت گرم رفیق 😎", "قربانت، هر وقت خواستی در خدمتم.", "خواهش می‌کنم ✌️", "خوشحالم که به کارت اومد 😊",
        "اختیار داری ❤️", "کاری نکردم رفیق 😄"
    ]
    goodbye = [
        "فعلاً رفیق 👋", "خداحافظ، مراقب خودت باش 🌹", "فعلاً، هر وقت کاری داشتی بیا 😄",
        "به امید دیدار 👋", "فعلاً داداش ✌️", "خدانگهدار رفیق ❤️", "فعلاً، روز خوبی داشته باشی.",
        "بای رفیق 😎", "هر وقت خواستی من اینجام 👋", "فعلاً، موفق باشی 🌹"
    ]
    generic = [
        "آره رفیق، متوجه شدم. بگو دقیقاً کدوم قسمت رو می‌خوای.",
        "باشه 😄 بگو بیشتر توضیح بدم.",
        "اوکی رفیق، گرفتم چی می‌گی. بریم جلو.",
        "حتماً. بگو منظورت دقیقاً چیه تا راهنماییت کنم.",
        "متوجه شدم 👌 اگه جزئیات بیشتری بدی بهتر می‌تونم راهنمایی کنم.",
        "آره، می‌تونیم حلش کنیم. بگو الان کجای کاری.",
        "باشه رفیق، قدم‌به‌قدم جلو می‌ریم.",
        "گرفتم 😎 بگو ادامه‌ش چی می‌شه.",
        "حتماً رفیق. هرچی می‌خوای بدونی بپرس.",
        "اوکی 👌 من در خدمتم."
    ]
    jokes = [
        "😂😂 خب رفیق، این یکی دیگه جالب بود!", "😂 دمت گرم، خوب گفتی.", "😄 گرفتم چی می‌گی رفیق.",
        "😂 آره، اینم یه مدلشه!", "😎😂 اوکی، متوجه شدم.", "😂 رفیق تو دیگه چی می‌گی!"
    ]

    # پاسخ‌های ترکیبی؛ 20×20×3 = 1200 حالت پایه
    bank = []
    for a in greetings:
        for b in warm:
            bank.append(a + "\n" + b)
    for a in greetings:
        for b in good:
            bank.append(a + "\n" + b)
    for a in good:
        for b in warm:
            bank.append(a + "\n" + b)
    bank.extend(thanks + goodbye + generic + jokes)
    # ترکیب‌های بیشتر برای بانک پاسخ؛ همه داخل خود برنامه تولید می‌شوند.
    for a in warm:
        for b in generic:
            bank.append(a + "\n" + b)

    # حذف تکراری‌ها و محدود کردن به حداقل ۱۰۰۰ پاسخ
    bank = list(dict.fromkeys(bank))
    _LOCAL_BANK = bank
    _LOCAL_GOOD = good
    _LOCAL_WARM = warm
    _LOCAL_GENERIC = generic
    _LOCAL_THANKS = thanks
    _LOCAL_GOODBYE = goodbye
    _LOCAL_JOKES = jokes
    return bank


def _pick_local(items, text):
    if not items:
        return "باشه رفیق 😄"
    # انتخاب پایدار برای یک پیام، ولی با متن‌های مختلف خروجی‌ها متنوع می‌شوند.
    n = int(hashlib.sha256(text.encode('utf-8')).hexdigest(), 16)
    return items[n % len(items)]


def _local_ai_reply(text):
    t = fa_to_en_digits(str(text).strip().lower())
    compact = re.sub(r'[\u200c\s]+', '', t)
    bank = _build_local_bank()

    # راهنمای واقعی ربات
    if any(x in t for x in ("چطوری سرویس بخر", "چطور سرویس بخر", "خرید سرویس", "سرویس بخرم", "میخوام سرویس بخر")):
        return None, "buy"
    if any(x in t for x in ("تمدید سرویس", "چطوری تمدید", "چطور تمدید", "تمدید کنم")):
        return None, "renew"
    if any(x in t for x in ("قیمت", "قیمت ها", "قیمت‌ها", "هزینه سرویس", "سرویس ها", "سرویس‌ها")):
        return None, "buy"
    if any(x in t for x in ("کمک", "راهنما", "چیکار میتونی", "چه کارهایی میتونی", "امکانات ربات")):
        return ("حتماً رفیق 👌\n\n"
                "از منوی پایین می‌تونی خرید سرویس، تمدید، مشاهده سرویس‌های خودت، کیف پول و پشتیبانی رو انجام بدی.\n\n"
                "اگه دنبال خریدی، روی «🛒 خرید سرویس» بزن؛ اگر مشکلی داری، «🎧 پشتیبانی» رو انتخاب کن."), "text"

    # سلام و احوالپرسی
    if compact in {"سلام", "سلم", "درود", "hello", "hi", "سلاممم", "سلام!", "سلام؟"} or compact.startswith("سلام"):
        return _pick_local([x for x in bank if x.startswith(("سلام", "درود"))], t), "text"
    if any(x in t for x in ("خوبی", "خوب هستی", "چطوری", "چهطوری", "حالت چطوره", "خوبی؟")):
        return _pick_local(_LOCAL_GOOD + _LOCAL_WARM, t), "text"
    if any(x in t for x in ("ممنون", "مرسی", "دمت گرم", "تشکر", "سپاس")):
        return _pick_local(_LOCAL_THANKS, t), "text"
    if any(x in t for x in ("خداحافظ", "فعلا", "فعلاً", "بای", "شب بخیر")):
        return _pick_local(_LOCAL_GOODBYE, t), "text"
    if any(x in t for x in ("😂", "خخخ", "هه", "🤣")):
        return _pick_local(_LOCAL_JOKES, t), "text"

    # مکالمه‌های رایج غیرسؤالی
    if any(x in t for x in ("چه خبر", "خبری", "خبرها", "چی میگذره")):
        return _pick_local([
            "همه‌چی مرتبه رفیق 😄 تو بگو چه خبر؟", "فعلاً اوضاع خوبه 😎 تو چه خبر؟",
            "خبر خاصی نیست، من در خدمتم 😄", "همه‌چی رو به راهه ✌️ بگو ببینم تو چه خبر؟"
        ], t), "text"
    if any(x in t for x in ("خسته", "حوصله ندارم", "کلافه")):
        return _pick_local([
            "یه نفس بکش رفیق 😄 بگو چی اذیتت کرده.", "اوکی، آروم 😌 بگو ببینم چی شده.",
            "حق داری، بعضی وقتا آدم خسته می‌شه. بگو چه کمکی ازم برمیاد."
        ], t), "text"

    # جواب عمومی طبیعی؛ بدون ادعای هوش ابری
    return _pick_local(_LOCAL_GENERIC + _LOCAL_WARM, t), "text"


async def vynexa_ai_generate_reply(user_text, history, cfg):
    # سازگاری با کد قبلی؛ این تابع دیگر هیچ درخواست اینترنتی نمی‌فرستد.
    answer, action = _local_ai_reply(user_text)
    if action != "text":
        return None
    return answer


async def vynexa_ai_fallback(update, context, text):
    uid = update.effective_user.id
    if not update.message or not text:
        return

    answer, action = _local_ai_reply(text)

    # درخواست‌هایی که باید وارد منوی واقعی ربات شوند.
    if action == "buy":
        return await buy(update, context)
    if action == "renew":
        return await renew_start(update, context)

    history = context.user_data.setdefault("vynexa_local_history", [])
    if answer:
        history.extend([
            {"role": "user", "content": str(text)[:2000]},
            {"role": "assistant", "content": answer[:2000]}
        ])
        context.user_data["vynexa_local_history"] = history[-12:]
        return await update.message.reply_text(answer, reply_markup=home(uid))

    return await update.message.reply_text(
        "باشه رفیق 😄 از منوی پایین انتخاب کن تا دقیق راهنماییت کنم.",
        reply_markup=home(uid)
    )


async def ai_faq_panel(update, context):
    buttons = [
        [InlineKeyboardButton('❓ V2Ray چیه؟', callback_data='ai_faq:v2ray')],
        [InlineKeyboardButton('🛒 چطور سرویس بخرم؟', callback_data='ai_faq:buy')],
        [InlineKeyboardButton('🔄 چطور تمدید کنم؟', callback_data='ai_faq:renew')],
        [InlineKeyboardButton('📦 حجم سرویس یعنی چی؟', callback_data='ai_faq:volume')],
        [InlineKeyboardButton('📅 مدت سرویس یعنی چی؟', callback_data='ai_faq:duration')],
        [InlineKeyboardButton('📱 چطور کانفیگ رو وارد کنم؟', callback_data='ai_faq:config')],
        [InlineKeyboardButton('⚠️ اگر وصل نشد چیکار کنم؟', callback_data='ai_faq:problem')],
        [InlineKeyboardButton('💰 قیمت سرویس‌ها چقدره؟', callback_data='ai_faq:prices')],
        [InlineKeyboardButton('🎟 کد تخفیف چیه؟', callback_data='ai_faq:discount')],
        [InlineKeyboardButton('💳 چطور پرداخت کنم؟', callback_data='ai_faq:payment')],
        [InlineKeyboardButton('💰 کیف پول چطور کار می‌کنه؟', callback_data='ai_faq:wallet')],
        [InlineKeyboardButton('➕ چطور کیف پول رو شارژ کنم؟', callback_data='ai_faq:wallet_topup')],
        [InlineKeyboardButton('🎲 گردونه شانس چیه؟', callback_data='ai_faq:dice')],
        [InlineKeyboardButton('🎁 تست رایگان چطوره؟', callback_data='ai_faq:test')],
        [InlineKeyboardButton('👥 زیرمجموعه‌گیری چطوره؟', callback_data='ai_faq:referral')],
        [InlineKeyboardButton('📦 سرویس‌های من کجاست؟', callback_data='ai_faq:services')],
        [InlineKeyboardButton('🔐 کانفیگ V2Ray کجاست؟', callback_data='ai_faq:v2ray_config')],
        [InlineKeyboardButton('⚡ V2Ray پرو چه فرقی داره؟', callback_data='ai_faq:pro')],
        [InlineKeyboardButton('💎 سرویس اقتصادی چیه؟', callback_data='ai_faq:economic')],
        [InlineKeyboardButton('🔷 سرویس عادی چیه؟', callback_data='ai_faq:normal')],
        [InlineKeyboardButton('⏳ سرویس من کی تموم میشه؟', callback_data='ai_faq:expiry')],
        [InlineKeyboardButton('📶 حجم باقی‌مانده رو چطور ببینم؟', callback_data='ai_faq:remaining')],
        [InlineKeyboardButton('🎧 چطور با پشتیبانی تماس بگیرم؟', callback_data='ai_faq:support')],
        [InlineKeyboardButton('❌ اگر پرداخت کردم ولی سفارش نیومد؟', callback_data='ai_faq:order_problem')],
        [InlineKeyboardButton('📸 رسید پرداخت رو کجا بفرستم؟', callback_data='ai_faq:receipt')],
        [InlineKeyboardButton('🔄 اگر کانفیگ قبلی کار نکرد؟', callback_data='ai_faq:old_config')],
    ]

    await update.message.reply_text(
        '🤖 سوالات هوش مصنوعی\n\n'
        'سوالت رو از لیست زیر انتخاب کن:',
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def ai_faq_callback(update, context):
    q = update.callback_query
    await q.answer()

    answers = {
        'v2ray':
            '🔹 V2Ray یک روش اتصال VPN است که برای اتصال امن به سرور استفاده می‌شود.',

        'buy':
            '🛒 از منوی اصلی روی «خرید سرویس» بزن و نوع سرویس، مدت و حجم موردنظرت را انتخاب کن.',

        'renew':
            '🔄 از منوی اصلی روی «تمدید سرویس» بزن و سرویس موردنظرت را انتخاب کن.',

        'volume':
            '📦 حجم یعنی مقدار دیتایی که سرویس می‌تواند مصرف کند؛ مثلاً ۵GB، ۱۰GB یا بیشتر.',

        'duration':
            '📅 مدت سرویس مشخص می‌کند سرویس تا چه زمانی فعال باشد؛ مثلاً ۱ ماهه یا ۳ ماهه.',

        'config':
            '📱 بعد از آماده‌شدن سرویس، کانفیگ را دریافت می‌کنی و باید آن را داخل برنامه سازگار با V2Ray وارد کنی.',

        'problem':
            '⚠️ اول اینترنت و فعال بودن سرویس را بررسی کن. اگر همچنان وصل نشد، از پشتیبانی کمک بگیر.',

        'prices':
            '💰 قیمت‌ها داخل بخش «خرید سرویس» نمایش داده می‌شوند و ممکن است بر اساس نوع، حجم و مدت متفاوت باشند.',

        'discount':
            '🎟 کد تخفیف را در مرحله پرداخت وارد کن. کد اصلی تخفیف Vynexa است.',

        'payment':
            '💳 پرداخت از طریق روش‌های پرداختی که داخل سفارش نمایش داده می‌شوند انجام می‌شود؛ از جمله کارت‌به‌کارت و کیف پول.',

        'wallet':
            '💰 کیف پول موجودی حساب توست و می‌توانی هنگام خرید از آن برای پرداخت سرویس استفاده کنی.',

        'wallet_topup':
            '➕ از بخش «کیف پول» گزینه شارژ را بزن، مبلغ موردنظر را وارد کن و رسید پرداخت را ارسال کن.',

        'dice':
            '🎲 گردونه شانس یک فرصت روزانه برای دریافت جایزه‌هایی مثل تخفیف، اعتبار کیف پول یا سرویس رایگان است.',

        'test':
            '🎁 برای بعضی سرویس‌ها امکان دریافت تست رایگان وجود دارد. از گزینه «دریافت تست رایگان» استفاده کن.',

        'referral':
            '👥 از بخش «زیرمجموعه‌گیری» لینک دعوت خودت را دریافت کن. با خرید موفق زیرمجموعه‌ها، پاداش دریافت می‌کنی.',

        'services':
            '📦 از منوی اصلی روی «سرویس‌های من» بزن تا سرویس‌های فعال حساب خودت را ببینی.',

        'v2ray_config':
            '🔐 کانفیگ V2Ray بعد از آماده‌شدن سفارش برایت ارسال می‌شود.',

        'pro':
            '⚡ V2Ray Pro سرویس نامحدود یک‌ماهه است و برای کاربری که حجم نامحدود می‌خواهد مناسب است.',

        'economic':
            '💎 سرویس اقتصادی گزینه مقرون‌به‌صرفه‌تر V2Ray است و در حجم‌ها و مدت‌های مختلف ارائه می‌شود.',

        'normal':
            '🔷 سرویس عادی V2Ray امکانات و پلن‌های بیشتری نسبت به اقتصادی دارد و قیمت آن بر اساس حجم و مدت تعیین می‌شود.',

        'expiry':
            '⏳ از بخش «سرویس‌های من» می‌توانی وضعیت سرویس و زمان باقی‌مانده آن را بررسی کنی.',

        'remaining':
            '📶 در بخش «سرویس‌های من» اطلاعات سرویس و در صورت در دسترس بودن، حجم باقی‌مانده نمایش داده می‌شود.',

        'support':
            '🎧 از منوی اصلی روی «پشتیبانی» بزن تا بتوانی درخواستت را برای پشتیبانی ارسال کنی.',

        'order_problem':
            '❌ اگر پرداخت انجام شده ولی سفارش نمایش داده نمی‌شود، رسید پرداخت را نگه دار و از بخش پشتیبانی پیگیری کن.',

        'receipt':
            '📸 بعد از انتخاب پرداخت کارت‌به‌کارت، رسید پرداخت را در همان گفت‌وگو ارسال کن تا برای بررسی مدیر ثبت شود.',

        'old_config':
            '🔄 اگر کانفیگ قبلی کار نمی‌کند، ابتدا وضعیت سرویس را بررسی کن و در صورت ادامه مشکل با پشتیبانی تماس بگیر.',
    }

    key = q.data.split(':', 1)[1]

    answer = answers.get(
        key,
        '❓ پاسخ این سوال پیدا نشد.'
    )

    await q.message.reply_text(answer)


async def inline_menu_router(update, context):
    """پل بین دکمه شیشه‌ای و منطق متنی قبلی ربات."""
    from types import SimpleNamespace

    query = update.callback_query
    if not query or not query.data or not query.data.startswith("menu:"):
        return
    label = query.data[5:]
    try:
        await query.answer()
    except Exception:
        pass

    # Main menu and purchase flow proceed directly; confirmations are only used by /emoji.
    original_message = query.message
    if original_message is not None:
        context.user_data["_last_inline_menu_chat_id"] = original_message.chat_id
        context.user_data["_last_inline_menu_message_id"] = original_message.message_id

    class MenuMessage:
        """Compatibility wrapper: menu stages edit the clicked inline message."""
        def __init__(self, base, text):
            self._base = base
            self.text = text

        def __getattr__(self, name):
            return getattr(self._base, name)

        async def reply_text(self, text, *args, **kwargs):
            # For service lists, edit the clicked menu into a heading first, then
            # send each service/order as its own message.
            mode = context.user_data.get('_menu_force_new_messages')
            if mode == 'first':
                context.user_data['_menu_force_new_messages'] = True
            elif mode:
                return await self._base.reply_text(text, *args, **kwargs)
            # Keep ordinary menu steps (and the first service-list heading) in place.
            try:
                return await self._base.edit_text(text=text, *args, **kwargs)
            except Exception as edit_error:
                try:
                    return await self._base.edit_caption(caption=text, **kwargs)
                except Exception:
                    # A few responses (e.g. a result that must be delivered
                    # separately) may not be editable; preserve the old behavior.
                    return await self._base.reply_text(text, *args, **kwargs)

    message = MenuMessage(original_message, label)
    routed_update = SimpleNamespace(
        message=message,
        effective_message=message,
        effective_user=query.from_user,
        effective_chat=query.message.chat if query.message else None,
        callback_query=None,
        update_id=update.update_id,
    )
    try:
        return await text_router(routed_update, context)
    except Exception as exc:
        print('INLINE MENU ACTION ERROR:', repr(exc)[:300])
        try:
            return await original_message.reply_text(
                '⚠️ اجرای این دکمه با خطا روبه‌رو شد. دوباره امتحان کن؛ اگر تکرار شد، خروجی ترموکس را بفرست.',
                reply_markup=home(query.from_user.id),
            )
        except Exception:
            return None


async def telegram_proxy_menu(update, context):
    """Return recent public-channel proxies with a per-user six-hour cooldown."""
    import html as _html
    import httpx
    from datetime import datetime
    uid = str(update.effective_user.id)
    usage_path = HOME / 'telegram_proxy_usage.json'
    # Merge both stores so a previous version's timestamp cannot be ignored just
    # because the JSON file already exists but is empty or stale.
    usage_file = read_json(usage_path, {})
    if not isinstance(usage_file, dict):
        usage_file = {}
    config = load_config()
    usage_config = config.get('telegram_proxy_last_used', {})
    if not isinstance(usage_config, dict):
        usage_config = {}
    usage = dict(usage_config)
    usage.update(usage_file)
    now = datetime.now().timestamp()
    try:
        last = max(float(usage_file.get(uid, 0) or 0), float(usage_config.get(uid, 0) or 0))
    except (TypeError, ValueError):
        last = 0.0
    wait = 21600 - (now - last)
    if wait > 0:
        hours = int(wait // 3600)
        minutes = int((wait % 3600) // 60)
        seconds = int(wait % 60)
        return await update.message.reply_text(
            f'⛔ هنوز امکان دریافت پروکسی نداری.\n\n'
            f'⏳ دریافت پروکسی فقط هر ۶ ساعت یک‌بار امکان‌پذیره.\n'
            f'زمان باقی‌مانده: {hours} ساعت و {minutes} دقیقه و {seconds} ثانیه',
            reply_markup=home(update.effective_user.id))

    sources = ['https://t.me/s/mproxy_ir', 'https://t.me/s/iMTProto']
    patterns = [r'https?://t\.me/proxy\?[^\s"\'<>]+', r'tg://proxy\?[^\s"\'<>]+']

    async def fetch_source(client, source):
        try:
            response = await client.get(source)
            if response.status_code != 200:
                return []
            page = _html.unescape(response.text).replace('&amp;', '&')
            links = []
            for pattern in patterns:
                for match in re.findall(pattern, page, flags=re.I):
                    url = match.rstrip(').,;!')
                    if url not in links:
                        links.append(url)
            # Telegram previews are newest-first; reverse to prioritize recent posts.
            return list(reversed(links))
        except Exception as exc:
            print('PROXY SOURCE ERROR:', source, repr(exc)[:120])
            return []

    try:
        timeout = httpx.Timeout(5.0, connect=3.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True,
                                     headers={'User-Agent': 'Mozilla/5.0'}) as client:
            batches = await asyncio.gather(*(fetch_source(client, source) for source in sources))
        found = []
        for batch in batches:
            for url in batch:
                if url not in found:
                    found.append(url)
                if len(found) >= 10:
                    break
            if len(found) >= 10:
                break
    except Exception as exc:
        print('PROXY FETCH ERROR:', repr(exc)[:120])
        found = []

    if not found:
        return await update.message.reply_text(
            '⚠️ فعلاً پروکسی قابل‌دسترسی از کانال‌ها پیدا نشد. کمی بعد دوباره امتحان کن.',
            reply_markup=home(update.effective_user.id))

    # Start cooldown only after a successful fetch and persist independently of config edits.
    usage[uid] = now
    # Save to both stores for compatibility with old bot versions and restarts.
    write_json(usage_path, usage)
    config['telegram_proxy_last_used'] = usage
    save_config(config)
    body = '🌐 پروکسی‌های جدید تلگرام\n\n' + '\n\n'.join(
        f'{i}. {url}' for i, url in enumerate(found, 1))
    return await update.message.reply_text(body, disable_web_page_preview=True,
                                           reply_markup=home(update.effective_user.id))


async def text_router(update, context):

    if not update.message or not update.message.text:
        return

    t = update.message.text.strip()
    uid = update.effective_user.id

    if context.user_data.get('awaiting_invoice_confirmation'):
        return await update.message.reply_text('🧾 اول فاکتور را از طریق دکمه «تأیید فاکتور و ادامه» تأیید کن؛ بعد اطلاعات مشتری را می‌گیریم.')

    # FIX: Handle account identity steps before any other pending state can consume them.
    # This also supports inline-menu callbacks routed through text_router.
    current_order = context.user_data.get('order')
    if current_order and t == '👤 اسم اکانت':
        context.user_data['identity_choice'] = 'name'
        return await update.message.reply_text(
            '👤 اسم اکانت را خودت وارد کن یا با دکمه زیر بساز:',
            reply_markup=kb([['✨ ساخت خودکار اسم اکانت'], ['🔙 برگشت']])
        )

    if current_order and t == '✨ ساخت خودکار اسم اکانت' and context.user_data.get('identity_choice') == 'name':
        existing = set()
        try:
            for saved in load_orders().values():
                for field in ('name', 'account_name', 'username'):
                    value = str(saved.get(field) or '').strip().lower()
                    if value:
                        existing.add(value)
        except Exception:
            pass
        generated = None
        for _ in range(100):
            candidate = 'vx_' + ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
            if candidate.lower() not in existing:
                generated = candidate
                break
        if not generated:
            generated = 'vx_' + secrets.token_hex(6)
        current_order['identity_type'] = 'name'
        current_order['name'] = generated
        current_order['account_name'] = generated
        current_order['username'] = generated
        context.user_data.pop('identity_choice', None)
        await update.message.reply_text(f'✅ اسم اکانت ساخته شد: {generated}')
        return await payment_menu(update, context)

    if current_order and context.user_data.get('identity_choice') == 'name' and t not in ('🔙 برگشت', '✨ ساخت خودکار اسم اکانت'):
        current_order['identity_type'] = 'name'
        current_order['name'] = t
        current_order['account_name'] = t
        current_order['username'] = t
        context.user_data.pop('identity_choice', None)
        return await payment_menu(update, context)

    # /emoji: admin sends the emoji directly after selecting a button.
    if context.user_data.get('waiting_custom_emoji') and is_admin(uid):
        target = context.user_data.get('vynexa_emoji_target')
        if not target:
            context.user_data.pop('waiting_custom_emoji', None)
            return await update.message.reply_text('❌ اول دکمه را انتخاب کن.')
        entities = list(getattr(update.message, 'entities', None) or []) + list(getattr(update.message, 'caption_entities', None) or [])
        custom_id = ''
        for ent in entities:
            if str(getattr(ent, 'type', '')) == 'custom_emoji' or str(getattr(getattr(ent, 'type', None), 'value', '')) == 'custom_emoji':
                custom_id = str(getattr(ent, 'custom_emoji_id', '') or '')
                if custom_id.isdigit(): break
        cfg = load_config()
        if custom_id.isdigit():
            mapping = cfg.setdefault('button_custom_emojis', {})
            mapping[target] = custom_id
            cfg.setdefault('button_custom_emoji_text', {}).pop(target, None)
            save_config(cfg)
            context.user_data.pop('waiting_custom_emoji', None)
            return await update.message.reply_text(f'✅ ایموجی سفارشی ثبت شد.\n\nدکمه: {target}\nشناسه: {custom_id}\n\nبرای دکمهٔ دیگر دوباره /emoji را بزن.')
        # Normal Unicode emoji can be used as a visible prefix.
        if len(t) <= 16 and not any(ch.isalnum() for ch in t) and any(ord(ch) > 127 for ch in t):
            cfg.setdefault('button_custom_emoji_text', {})[target] = t
            cfg.setdefault('button_custom_emojis', {}).pop(target, None)
            save_config(cfg)
            context.user_data.pop('waiting_custom_emoji', None)
            return await update.message.reply_text(f'✅ ایموجی ثبت شد.\n\nدکمه: {target}\nایموجی: {t}\n\nبرای دکمهٔ دیگر دوباره /emoji را بزن.')
        return await update.message.reply_text('⚠️ لطفاً فقط یک ایموجی بفرست؛ اگر ایموجی سفارشی پریمیوم است، خود ایموجی را مستقیماً ارسال کن.')

    # Keep announcement flow at the very top so other pending states
    # cannot consume the admin's "📢 اطلاعیه" button text.
    if t == "📢 اطلاعیه" and is_admin(uid):
        context.user_data.pop("channel_send", None)
        return await announce(update, context)

    if context.user_data.get("channel_send") and is_admin(uid):
        return await do_send_to_channel(update, context)

    remember_user(uid)

    # ===== CUSTOMER TICKET =====
    if context.user_data.get("waiting_ticket"):
        oid = str(context.user_data.pop("waiting_ticket"))
        ticket_text = t

        if not ticket_text:
            return await update.message.reply_text("🎫 لطفاً مشکل سرویس را بنویسید.")

        orders = load_orders()
        o = orders.get(oid)

        if not o or str(o.get("user_id")) != str(uid):
            return await update.message.reply_text("❌ سرویس پیدا نشد.")

        o["ticket"] = {
            "order_id": oid,
            "user_id": str(uid),
            "text": ticket_text,
            "created_at": datetime.now().isoformat(),
            "status": "open"
        }

        orders[oid] = o
        save_orders(orders)

        await update.message.reply_text(
            "🎫 تیکت پشتیبانی ثبت شد.\n\n"
            "مشکل شما برای پشتیبانی ارسال شد. 💙"
        )

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📥 دریافت اطلاعات سرویس",
                callback_data=f"ticketinfo:{oid}"
            )],
            [InlineKeyboardButton(
                "🎫 تیکت ثبت شده کاربر",
                callback_data=f"ticketview:{oid}"
            )]
        ])

        await context.bot.send_message(
            admin_id(),
            "🎫 تیکت جدید پشتیبانی\n\n"
            + order_summary(o)
            + "\n\n📝 مشکل مشتری:\n"
            + ticket_text,
            reply_markup=markup
        )
        return

    # ===== ADMIN TICKET REPLY =====
    if context.user_data.get("admin_ticket_reply"):
        if not is_admin(uid):
            context.user_data.pop("admin_ticket_reply", None)
            return

        oid = str(context.user_data.pop("admin_ticket_reply"))
        reply_text = t

        if not reply_text:
            return await update.message.reply_text(
                "💬 متن پاسخ را ارسال کنید."
            )

        orders = load_orders()
        o = orders.get(oid)

        if not o:
            return await update.message.reply_text(
                "❌ سرویس پیدا نشد."
            )

        ticket = o.get("ticket") or {}
        ticket["admin_reply"] = reply_text
        ticket["answered_at"] = datetime.now().isoformat()
        ticket["status"] = "answered"

        o["ticket"] = ticket
        orders[oid] = o
        save_orders(orders)

        try:
            await context.bot.send_message(
                int(o["user_id"]),
                "🎫 پاسخ پشتیبانی\n\n" + reply_text
            )
            return await update.message.reply_text(
                "✅ پاسخ تیکت برای مشتری ارسال شد."
            )
        except Exception:
            return await update.message.reply_text(
                "❌ ارسال پاسخ انجام نشد."
            )

    # کد تخفیف
    if context.user_data.get("waiting_discount"):
        return await vynexa_discount_handler(update, context)

    # Normalize menu choices
    choice_map = {
        "🌐 V2Ray": "V2Ray",
        "🟢 WireGuard": "wireguard",
        "🟢 wireguard": "wireguard",
        "🔵 OpenVPN": "openvpn",
        "🔵 openvpn": "openvpn",
        "🟢 OpenVPN": "openvpn",
        "💚 اقتصادی": "اقتصادی",
        "🔵 عادی": "عادی",
        "🟣 پرو": "پرو",
        "💚 اقتصادی-حجمی": "اقتصادی-حجمی",
        "🔵 عادی-حجمی": "عادی-حجمی",
        "🟣 پرو- نامحدود حجم": "پرو- نامحدود حجم",
        "🧪 تست رایگان": "تست رایگان",
        "🧪 تست اقتصادی": "تست اقتصادی",
        "🧪 تست عادی": "تست عادی",
        "🟣 تست پرو": "تست پرو",
        "📅 1 ماهه": "1 ماهه",
        "📅 2 ماهه": "2 ماهه",
        "📅 3 ماهه": "3 ماهه",
    }

    if t == "🤖 سوالات هوش مصنوعی":
        return await ai_faq_panel(update, context)

    if t == "👥 زیرمجموعه‌گیری":
        if is_admin(uid) and context.user_data.get("admin_mode"):
            return await referral_admin_panel(update, context)
        return await referral_panel(update, context)

    if t == "📦 سرویس‌های من":
        return await services(update, context)

    if t == "📦 سرویس‌های تأیید شده" and is_admin(uid):
        return await approved_services(update, context)

    t = choice_map.get(t, t)
    # Normalize visual prefixes so inline/reply labels follow the same purchase flow.
    t = t.replace('👤 ', '').replace('👥 ', '')

    if t.startswith("📦 " ):
        t = t[len("📦 "):]

    if is_admin(uid) and context.user_data.get("announce"):
        return await do_announce(update, context)

    if t == "/admin":
        return await admin_cmd(update, context)

    if not bot_enabled() and not is_admin(uid):
        return await update.message.reply_text(
            "🔴 ربات فعلاً خاموش است."
        )

    if t == "🛒 خرید سرویس":
        return await buy(update, context)
    if t == '🌐 پروکسی تلگرام':
        return await telegram_proxy_menu(update, context)

    # V2Ray dedicated flow
    if t == 'V2Ray' or t.lower() == 'v2ray': return await v2ray_menu(update, context)
    # WireGuard 1-month speed selection
    if context.user_data.get('service') and str(context.user_data.get('service')).lower() == 'wireguard':
        item = context.user_data.get('item', {})
        if t == '🔙 برگشت':
            context.user_data.clear(); return await buy(update, context)
        for plan, value in item.items():
            if isinstance(value, (int, float)) and t in (f'⚡ 1 ماهه | 🚀 {plan} — {shown_price(value)}', f'1 ماهه | 🚀 {plan} — {shown_price(value)}'):
                o={'id':make_order_id(),'user_id':uid,'service':'WireGuard','volume':'-','duration':'1 ماهه','speed':str(plan),'price':int(value),'status':'draft','created_at':datetime.now().isoformat()}
                context.user_data['order']=o
                return await show_invoice_then_identity(update, context)
    if context.user_data.get('v2ray_flow'):
        tier_map = {'اقتصادی':'economic', 'اقتصادی-حجمی':'economic', 'عادی':'normal', 'عادی-حجمی':'normal', 'پرو':'pro', 'پرو- نامحدود حجم':'pro'}
        if t in tier_map: return await v2ray_duration_menu(update, context, tier_map[t])
        if t == 'تک کاربر' and context.user_data.get('v2ray_tier') == 'pro':
            context.user_data['pro_user_mode'] = 'single'
            return await update.message.reply_text('👤 پرو نامحدود حجم — تک کاربر\n\nمدت را انتخاب کن:', reply_markup=kb([['📅 1 ماهه'], ['📅 2 ماهه'], ['📅 3 ماهه'], ['🔙 برگشت']]))
        if t == 'چند کاربر' and context.user_data.get('v2ray_tier') == 'pro':
            context.user_data['pro_user_mode'] = 'multi'
            context.user_data['pro_users'] = 'چند کاربر'
            return await create_v2ray_order(update, context, 'نامحدود حجم — چند کاربر', 220000, '1 ماهه')
        if t in ('1 ماهه', '2 ماهه', '3 ماهه') and context.user_data.get('v2ray_tier') == 'pro' and context.user_data.get('pro_user_mode') == 'single':
            prices = {'1 ماهه': 100000, '2 ماهه': 200000, '3 ماهه': 300000}
            return await create_v2ray_order(update, context, 'نامحدود حجم — تک کاربر', prices[t], t)
        if t == 'تست رایگان': return await v2ray_test_menu(update, context)
        if t == 'تست اقتصادی': return await handle_v2ray_test(update, context, 'economic')
        if t == 'تست عادی': return await handle_v2ray_test(update, context, 'normal')
        if t == 'تست پرو': return await handle_v2ray_test(update, context, 'pro')
        if t in ('1 ماهه','3 ماهه') and context.user_data.get('v2ray_tier'):
            context.user_data['v2ray_duration'] = t
            return await v2ray_volume_menu(update, context)
        # Handle the custom-volume button whether or not the package emoji was stripped.
        if t in ('حجم دلخواه (۵GB به بالا)', '📦 حجم دلخواه (۵GB به بالا)'):
            context.user_data['v2ray_wait_custom'] = False
            context.user_data['v2ray_custom_gb'] = 5
            return await show_v2ray_custom_timeline(update.message, context, 5)
        # The 1-month economic/normal plans are generated from fixed prices above,
        # so handle them directly instead of relying on config.json plan entries.
        if context.user_data.get('v2ray_duration') == '1 ماهه' and context.user_data.get('v2ray_tier') in ('economic', 'normal'):
            match = re.fullmatch(r'(\d+)GB\s*—\s*([\d,٬]+)(?:\s*تومان)?', fa_to_en_digits(t).replace('٬', ','))
            if match:
                gb = int(match.group(1))
                button_price = int(match.group(2).replace(',', ''))
                tier = context.user_data.get('v2ray_tier')
                if 5 <= gb <= 10:
                    prices = {'economic': {5:45000, 6:50000, 7:55000, 8:60000, 9:65000, 10:70000},
                              'normal': {5:75000, 6:84000, 7:93000, 8:102000, 9:111000, 10:120000}}
                    expected = prices[tier][gb]
                    if button_price == int(round(expected * PRICE_MARKUP)):
                        return await create_v2ray_order(update, context, f'{gb}GB', expected, '1 ماهه')
        if context.user_data.get('v2ray_wait_custom'):
            try:
                gb = int(fa_to_en_digits(t).replace(',','').replace('٬','').replace('GB','').replace('gb','').strip())
            except Exception:
                return await update.message.reply_text('❌ حجم باید عدد باشد. مثال: 15')
            if gb < 5:
                return await update.message.reply_text('❌ حداقل حجم ۵GB است.')
            tier = context.user_data.get('v2ray_tier')
            if tier == 'economic': price = 45000 + (gb-5)*5000 if gb <= 10 else gb*6000
            else: price = 75000 + (gb-5)*9000 if gb <= 10 else gb*10000
            return await create_v2ray_order(update, context, f'{gb}GB', price, '1 ماهه')
        if context.user_data.get('v2ray_duration') and t not in ('🔙 برگشت',):
            tier = context.user_data.get('v2ray_tier'); duration = context.user_data.get('v2ray_duration')
            data = v2ray_item().get(tier, {})
            if duration == '1 ماهه' and tier == 'pro' and ('نامحدود' in t): return await create_v2ray_order(update, context, 'نامحدود', 220000, duration)
            for volume, price in data.get(duration, {}).items():
                if t == f'{volume} — {shown_price(price)}': return await create_v2ray_order(update, context, volume, price, duration)
        if t == '🔙 برگشت':
            # Always move exactly one level back in the V2Ray flow.
            if context.user_data.get('v2ray_wait_custom'):
                context.user_data.pop('v2ray_wait_custom', None)
                return await v2ray_volume_menu(update, context)
            if context.user_data.get('v2ray_duration'):
                context.user_data.pop('v2ray_duration', None)
                return await v2ray_duration_menu(update, context, context.user_data.get('v2ray_tier'))
            if context.user_data.get('v2ray_tier'):
                context.user_data.pop('v2ray_tier', None)
                return await v2ray_menu(update, context)
            context.user_data.pop('v2ray_flow', None)
            return await buy(update, context)
    if t=='🔄 تمدید سرویس': return await renew_start(update,context)
    if t=='📦 سرویس‌های من': return await services(update,context)
    if t=='🎧 پشتیبانی': return await support(update,context)
    if t=='🎲 گردان شانس': return await vynexa_dice(update,context)
    if t=='🎲 گردونه شانس' and is_admin(uid): return await dice_admin_panel(update,context)
    if t=='💰 کیف پول': return await wallet(update,context)
    if t=='🎟 کد تخفیف دارم':
        context.user_data['waiting_discount'] = True
        return await update.message.reply_text(
            "🎟 کد تخفیف خود را وارد کنید:"
        )

    if t=='💳 پرداخت باقی‌مانده با کارت‌به‌کارت':
        o = context.user_data.get('order')
        if not o:
            return await update.message.reply_text('❌ سفارش فعالی پیدا نشد.')
        remaining = int(o.get('remaining_price', 0) or 0)
        if remaining <= 0:
            return await update.message.reply_text('✅ مبلغ سفارش قبلاً کامل پرداخت شده است.')
        context.user_data['waiting_receipt'] = True
        card = load_config().get('card_number','شماره کارت در config.json تنظیم نشده')
        owner = load_config().get('card_name','نام صاحب کارت')
        return await update.message.reply_text(
            f"💳 پرداخت باقی‌مانده سفارش\n\n"
            f"💰 مبلغ قابل پرداخت: {money(remaining)}\n"
            f"💳 شماره کارت: {card}\n"
            f"👤 به نام: {owner}\n\n"
            "📸 بعد از پرداخت، عکس رسید را ارسال کن."
        )

    if t=='➕ شارژ کیف پول و پرداخت باقی‌مانده':
        o = context.user_data.get('order')
        if not o:
            return await update.message.reply_text('❌ سفارش فعالی پیدا نشد.')
        remaining = int(o.get('remaining_price', 0) or 0)
        if remaining <= 0:
            return await update.message.reply_text('✅ مبلغ سفارش قبلاً کامل پرداخت شده است.')
        context.user_data['wallet_topup'] = True
        context.user_data['wallet_topup_for_order'] = o.get('id')
        return await update.message.reply_text(
            f"💰 مبلغ باقی‌مانده سفارش: {money(remaining)}\n\n"
            "مبلغی که می‌خواهی به کیف پول اضافه کنی را به تومان وارد کن:"
        )

    if t=='➕ شارژ کیف پول': context.user_data['wallet_topup']=True; return await update.message.reply_text('💰 مبلغ شارژ را به تومان وارد کن:')
    if context.user_data.get('wallet_topup'):
        try: amount=int(t.replace(',','').replace('٬',''))
        except: return await update.message.reply_text('❌ مبلغ باید عدد باشد.')
        if amount<=0: return await update.message.reply_text('❌ مبلغ نامعتبر است.')
        context.user_data.pop('wallet_topup',None)
        oid=make_order_id()
        o={'id':oid,'user_id':uid,'type':'wallet_topup','amount':amount,'status':'pending_wallet','created_at':datetime.now().isoformat()}
        linked_order = context.user_data.pop('wallet_topup_for_order', None)
        if linked_order:
            o['linked_order_id'] = linked_order
        orders=load_orders()
        orders[oid]=o
        save_orders(orders)
        card=load_config().get('card_number','شماره کارت در config.json تنظیم نشده'); owner=load_config().get('card_name','نام صاحب کارت')
        context.user_data['wallet_receipt_order']=oid
        return await update.message.reply_text(f'💳 شارژ کیف پول\n\n💰 مبلغ: {money(amount)}\n💳 شماره کارت: {card}\n👤 به نام: {owner}\n\nبعد از پرداخت، عکس رسید را ارسال کن.')
    if t=='📢 اطلاعیه' and is_admin(uid): return await announce(update,context)
    if t=='📢 ارسال پیام به کانال' and is_admin(uid): return await send_to_channel(update,context)
    if t=='🤖 ربات روشن/خاموش' and is_admin(uid): return await toggle_bot(update,context)
    if t=='⚙️ مدیریت VPN' and is_admin(uid): return await manage_vpn(update,context)
    if t=='📦 سرویس‌های تأیید شده' and is_admin(uid): return await approved_services(update,context)
    if t=='👥 سرویس مشتری‌ها' and is_admin(uid): return await customer_services(update,context)
    if t=='🚀 ارسال کانفیگ' and is_admin(uid): return await send_config_menu(update,context)
    if t=='🔙 خروج به صفحه اصلی': context.user_data.clear(); return await update.message.reply_text('🏠 صفحه اصلی',reply_markup=home(uid))
    if t=='➕ افزودن VPN' and is_admin(uid): return await add_vpn_start(update,context)
    if t=='✏️ ویرایش VPN' and is_admin(uid): return await edit_vpn_start(update,context)
    if t=='🗑 حذف VPN' and is_admin(uid): return await delete_vpn_start(update,context)
    if t=='🔙 برگشت':
        context.user_data.clear(); return await update.message.reply_text('🏠 صفحه اصلی',reply_markup=home(uid))

    if is_admin(uid) and context.user_data.get('delivery_order'):
        return await save_delivery_item(update,context,{'type':'text','value':t})

    if is_admin(uid) and context.user_data.get('vpn_add'):
        st=context.user_data['vpn_add']['step']; nv=context.user_data['vpn_add']
        if st=='name': nv['name']=t; nv['step']='volume'; return await update.message.reply_text('📦 حجم را وارد کن:')
        if st=='volume': nv['volume']=t; nv['step']='duration'; return await update.message.reply_text('⏳ مدت را وارد کن:')
        if st=='duration': nv['duration']=t; nv['step']='speed'; return await update.message.reply_text('🚀 سرعت را وارد کن:')
        if st=='speed': nv['speed']=t; nv['step']='price'; return await update.message.reply_text('💰 قیمت را به تومان وارد کن:')
        if st=='price':
            try: nv['price']=int(t.replace(',','').replace('٬',''))
            except: return await update.message.reply_text('❌ قیمت باید عدد باشد. دوباره وارد کن:')
            name=nv['name']; data={k:v for k,v in nv.items() if k!='step'}; data['active']=True
            c=load_config(); c.setdefault('prices',{})[name]=data; save_config(c); context.user_data.clear()
            return await update.message.reply_text(f'✅ VPN «{name}» اضافه شد.',reply_markup=home(uid))

    if is_admin(uid) and context.user_data.get('vpn_delete_select'):
        c=load_config();
        if t in c.get('prices',{}): c['prices'].pop(t); save_config(c); context.user_data.clear(); return await update.message.reply_text(f'🗑 «{t}» حذف شد.',reply_markup=home(uid))

    if is_admin(uid) and context.user_data.get('vpn_edit_select'):
        if t in load_config().get('prices',{}): context.user_data.pop('vpn_edit_select'); return await edit_field_menu(update,context,t)

    if is_admin(uid) and context.user_data.get('vpn_edit_name'):
        name=context.user_data['vpn_edit_name']
        fields={'📦 حجم':'volume','⏳ مدت':'duration','🚀 سرعت':'speed','💰 قیمت':'price','✏️ نام':'name'}
        if t in fields:
            context.user_data['edit_field']=fields[t]
            return await update.message.reply_text(f'✏️ مقدار جدید را برای «{t}» وارد کن:')
        if context.user_data.get('edit_field'):
            field=context.user_data.pop('edit_field'); c=load_config(); item=c['prices'][name]
            if field=='price':
                try: t=int(t.replace(',','').replace('٬',''))
                except: return await update.message.reply_text('❌ قیمت باید عدد باشد. دوباره وارد کن:')
            if field=='name':
                new=str(t).strip(); c['prices'][new]=item; c['prices'].pop(name)
            else: item[field]=t; c['prices'][name]=item
            save_config(c); context.user_data.clear(); return await update.message.reply_text('✅ ویرایش با موفقیت انجام شد.',reply_markup=home(uid))

    if context.user_data.get('renew_wait_name'):
        wanted = str(t).strip()
        if wanted == '🔙 برگشت':
            context.user_data.clear(); return await update.message.reply_text('🏠 صفحه اصلی', reply_markup=home(uid))
        mine = customer_services_for_renewal(uid)
        exact = []
        for oid, o in mine:
            ident = renewal_identity(o)
            if ident == wanted or ident.casefold() == wanted.casefold():
                exact.append((oid, o))
        if not exact:
            return await update.message.reply_text('❌ سرویسی با این نام پیدا نشد.\n\nنام سرویس را دقیقاً مثل فهرست بالا ارسال کن:')
        if len(exact) == 1:
            context.user_data.pop('renew_wait_name', None)
            return await show_renewal_confirmation(update, context, exact[0][1], exact[0][0])
        buttons = [[InlineKeyboardButton(f'{o.get("volume", "-")} — {o.get("duration", "-")}', callback_data=f'renewpick:{oid}')] for oid,o in exact]
        context.user_data.pop('renew_wait_name', None)
        return await update.message.reply_text('🔎 چند سرویس با این نام پیدا شد؛ سرویس موردنظر را انتخاب کن:', reply_markup=InlineKeyboardMarkup(buttons))

    if context.user_data.get('order'):
        o=context.user_data['order']
        if t=='👤 اسم اکانت':
            context.user_data['identity_choice']='name'
            return await update.message.reply_text(
                '👤 اسم اکانت را خودت وارد کن یا با دکمه زیر بساز:',
                reply_markup=kb([['✨ ساخت خودکار اسم اکانت'], ['🔙 برگشت']])
            )
        if t=='✨ ساخت خودکار اسم اکانت' and context.user_data.get('identity_choice')=='name':
            existing = set()
            try:
                for saved in load_orders().values():
                    for field in ('name', 'account_name', 'username'):
                        value = str(saved.get(field) or '').strip().lower()
                        if value:
                            existing.add(value)
            except Exception:
                pass
            for _ in range(20):
                generated = 'vx_' + ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
                if generated.lower() not in existing:
                    break
            o['identity_type']='name'
            o['name']=generated
            o['account_name']=generated
            o['username']=generated
            context.user_data.pop('identity_choice', None)
            await update.message.reply_text(f'✅ اسم اکانت ساخته شد: `{generated}`', parse_mode='Markdown')
            return await payment_menu(update,context)
        if t=='📱 شماره تلفن': context.user_data['identity_choice']='phone'; return await update.message.reply_text('📱 شماره تلفن را وارد کن:')
        if context.user_data.get('identity_choice')=='name':
            o['identity_type']='name'; o['name']=t; o['account_name']=t; o['username']=t
            context.user_data.pop('identity_choice'); return await payment_menu(update,context)
        if context.user_data.get('identity_choice')=='phone': o['identity_type']='phone'; o['phone']=t; context.user_data.pop('identity_choice'); return await payment_menu(update,context)
        if t=='💳 کارت به کارت': return await show_card(update,context)
        if t=='💰 استفاده از کیف پول': return await use_wallet(update,context)

    # VPN name selection - accept both display names and config key casing
    prices=load_config().get('prices',{})
    if t in prices and isinstance(prices[t],dict):
        return await choose_vpn(update,context,t)
    low_t = str(t).strip().lower()
    if low_t in ('wireguard','openvpn','v2ray'):
        for key, value in prices.items():
            if str(key).strip().lower() == low_t and isinstance(value,dict):
                return await choose_vpn(update,context,key)
        if low_t == 'v2ray':
            return await v2ray_menu(update, context)

    service=context.user_data.get('service'); item=context.user_data.get('item')
    if service and isinstance(item,dict):
        if t == '🔙 برگشت':
            context.user_data.clear()
            return await buy(update, context)

        # OpenVPN: handle plan buttons explicitly and normalize their text.
        if str(service).strip().lower() == 'openvpn':
            normalized = str(t).strip()
            if normalized.startswith('📦 '):
                normalized = normalized[3:].strip()
            for plan, value in item.items():
                if not isinstance(value, (int, float)):
                    continue
                if str(plan).strip() == normalized:
                    duration = '-'
                    volume = str(plan)
                    m = re.match(r'\s*(.+?)\s*\|\s*(.+?)\s*$', str(plan))
                    if m:
                        duration, volume = m.group(1).strip(), m.group(2).strip()
                    o = {
                        'id': make_order_id(), 'user_id': uid, 'service': service,
                        'volume': volume, 'duration': duration, 'speed': '-',
                        'price': int(value), 'status': 'draft',
                        'created_at': datetime.now().isoformat()
                    }
                    context.user_data['order'] = o
                    return await show_invoice_then_identity(update, context)

        # Other price-table VPNs.
        for plan, value in item.items():
            if str(plan).strip() == t.strip() and isinstance(value,(int,float)):
                duration = '-'
                volume = str(plan)
                m = re.match(r'\s*(.+?)\s*\|\s*(.+?)\s*$', str(plan))
                if m:
                    duration, volume = m.group(1).strip(), m.group(2).strip()
                o={'id':make_order_id(),'user_id':uid,'service':service,'volume':volume,'duration':duration,'speed':item.get('speed','-'),'price':int(value),'status':'draft','created_at':datetime.now().isoformat()}
                context.user_data['order']=o
                return await show_invoice_then_identity(update, context)

    return


async def dice_delete_callback(update, context):
    q = update.callback_query

    if not is_admin(q.from_user.id):
        await q.answer("⛔ دسترسی ندارید.", show_alert=True)
        return

    data = q.data or ""

    if not data.startswith("dice_delete:"):
        return

    uid = data.split(":", 1)[1]

    users = load_users()
    u = users.setdefault(uid, {})

    u["dice_blocked"] = True
    u["dice_extra_spins"] = 0

    save_users(users)

    await q.answer("🗑 گردونه این کاربر حذف شد.", show_alert=True)

    try:
        await context.bot.send_message(
            int(uid),
            "⛔ دسترسی شما به گردونه شانس غیرفعال شد."
        )
    except Exception:
        pass


async def buy_confirmation_callback(update, context):
    q = update.callback_query
    await q.answer()
    action = (q.data or '').split(':')[-1]
    label = context.user_data.get('_pending_confirm_label')
    if action == 'no':
        context.user_data.pop('_pending_confirm_label', None)
        # Return to the relevant previous selection screen.
        if label == '🛒 خرید سرویس':
            from types import SimpleNamespace
            class BuyMessage:
                def __init__(self, base): self._base=base; self.text='🛒 خرید سرویس'
                def __getattr__(self, name): return getattr(self._base, name)
                async def reply_text(self, text, *args, **kwargs):
                    try: return await self._base.edit_text(text=text, *args, **kwargs)
                    except Exception: return await self._base.reply_text(text, *args, **kwargs)
            msg=BuyMessage(q.message)
            routed=SimpleNamespace(message=msg, effective_message=msg, effective_user=q.from_user, effective_chat=q.message.chat if q.message else None, callback_query=None, update_id=update.update_id)
            return await buy(routed, context)
        if label == '🌐 V2Ray' or label.startswith(('🟢 WireGuard', '🔵 OpenVPN')):
            from types import SimpleNamespace
            class BuyMessage:
                def __init__(self, base, text): self._base=base; self.text=text
                def __getattr__(self, name): return getattr(self._base, name)
                async def reply_text(self, text, *args, **kwargs):
                    try: return await self._base.edit_text(text=text, *args, **kwargs)
                    except Exception: return await self._base.reply_text(text, *args, **kwargs)
            msg=BuyMessage(q.message, '🛒 خرید سرویس')
            routed=SimpleNamespace(message=msg, effective_message=msg, effective_user=q.from_user, effective_chat=q.message.chat if q.message else None, callback_query=None, update_id=update.update_id)
            return await buy(routed, context)
        if label in ('💚 اقتصادی-حجمی', '🔵 عادی-حجمی', '🟣 پرو- نامحدود حجم', '💚 اقتصادی', '🔵 عادی', '🟣 پرو'):
            return await q.edit_message_text('نوع سرویس را انتخاب کن:', reply_markup=kb([['💚 اقتصادی-حجمی'], ['🔵 عادی-حجمی'], ['🟣 پرو- نامحدود حجم'], ['🧪 تست رایگان'], ['🔙 برگشت']]))
        if context.user_data.get('v2ray_flow'):
            tier = context.user_data.get('v2ray_tier')
            if label.startswith('📅') and tier in ('economic', 'normal'):
                return await q.edit_message_text('مدت سرویس را انتخاب کن:', reply_markup=kb([['📅 1 ماهه'], ['📅 3 ماهه'], ['🔙 برگشت']]))
            if tier == 'pro' and context.user_data.get('pro_user_mode') == 'single':
                markup = kb([['📅 1 ماهه'], ['📅 2 ماهه'], ['📅 3 ماهه'], ['🔙 برگشت']])
                return await q.edit_message_text('مدت پرو تک‌کاربر را دوباره انتخاب کن:', reply_markup=markup)
            if tier == 'pro':
                return await q.edit_message_text('تعداد کاربران را انتخاب کن:', reply_markup=kb([['👤 تک کاربر'], ['👥 چند کاربر'], ['🔙 برگشت']]))
            if tier:
                return await q.edit_message_text('نوع سرویس را دوباره انتخاب کن:', reply_markup=kb([['💚 اقتصادی-حجمی'], ['🔵 عادی-حجمی'], ['🟣 پرو- نامحدود حجم'], ['🧪 تست رایگان'], ['🔙 برگشت']]))
        return await q.edit_message_text('🏠 منوی اصلی', reply_markup=home(q.from_user.id))
    if not label:
        return await q.edit_message_text('⚠️ انتخابی برای تأیید پیدا نشد.', reply_markup=home(q.from_user.id))
    context.user_data.pop('_pending_confirm_label', None)
    # Reuse the normal text router with the existing inline-message adapter.
    from types import SimpleNamespace
    class ConfirmMessage:
        def __init__(self, base, text): self._base=base; self.text=text
        def __getattr__(self, name): return getattr(self._base, name)
        async def reply_text(self, text, *args, **kwargs):
            try: return await self._base.edit_text(text=text, *args, **kwargs)
            except Exception: return await self._base.reply_text(text, *args, **kwargs)
    msg=ConfirmMessage(q.message, label)
    routed=SimpleNamespace(message=msg, effective_message=msg, effective_user=q.from_user, effective_chat=q.message.chat if q.message else None, callback_query=None, update_id=update.update_id)
    # Do not re-enter the confirmation branch: this is already confirmed.
    return await text_router(routed, context)


async def callback(update, context):
    q=update.callback_query; d=q.data; uid=q.from_user.id
    if d.startswith('invoiceconfirm:'):
        action = d.split(':', 1)[1]
        order = context.user_data.get('order')
        if not order:
            return await q.answer('سفارش فعالی پیدا نشد.', show_alert=True)
        if action == 'yes':
            context.user_data['invoice_confirmed'] = True
            context.user_data.pop('awaiting_invoice_confirmation', None)
            await q.answer('فاکتور تأیید شد.')
            return await q.edit_message_text(
                '✅ فاکتور تأیید شد.\n\nحالا روش ثبت مشخصات مشتری را انتخاب کن:',
                reply_markup=kb([['👤 اسم اکانت'], ['📱 شماره تلفن'], ['🔙 برگشت']])
            )
        context.user_data.pop('order', None)
        context.user_data.pop('awaiting_invoice_confirmation', None)
        context.user_data.pop('invoice_confirmed', None)
        context.user_data.pop('identity_choice', None)
        await q.answer('سفارش لغو شد.')
        return await q.edit_message_text('❌ سفارش لغو شد. هر زمان خواستی می‌توانی دوباره خرید کنی.', reply_markup=home(uid))
    if d.startswith('v2custom:'):
        if not context.user_data.get('v2ray_tier'):
            return await q.answer('انتخاب حجم منقضی شده؛ دوباره از خرید V2Ray وارد شو.', show_alert=True)
        action = d.split(':', 2)
        current = int(context.user_data.get('v2ray_custom_gb', 5) or 5)
        if len(action) >= 3 and action[1] == 'step':
            try: step = int(action[2])
            except Exception: step = 5
            new_gb = max(5, min(1000, current + step))
            await q.answer()
            return await show_v2ray_custom_timeline(q.message, context, new_gb, edit=True)
        if len(action) >= 2 and action[1] == 'back':
            await q.answer()
            context.user_data.pop('v2ray_custom_gb', None)
            context.user_data['v2ray_duration'] = '1 ماهه'
            tier = context.user_data.get('v2ray_tier', 'economic')
            vals = {'economic': [45000,50000,55000,60000,65000,70000], 'normal': [75000,84000,93000,102000,111000,120000]}.get(tier)
            if vals:
                rows = [[f'📦 {gb}GB — {shown_price(price)}'] for gb, price in zip(range(5, 11), vals)]
                rows.extend([['📦 حجم دلخواه (۵GB به بالا)'], ['🔙 برگشت']])
                return await q.edit_message_text('📦 حجم سرویس را انتخاب کن:', reply_markup=kb(rows))
            return await q.edit_message_text('مدت سرویس را انتخاب کن:', reply_markup=kb([['📅 1 ماهه'], ['📅 3 ماهه'], ['🔙 برگشت']]))
        if len(action) >= 2 and action[1] == 'confirm':
            gb = max(5, min(1000, current))
            tier = context.user_data.get('v2ray_tier', 'economic')
            base_price = (45000 + (gb-5)*5000 if gb <= 10 else gb*6000) if tier == 'economic' else (75000 + (gb-5)*9000 if gb <= 10 else gb*10000)
            final_price = int(round(base_price * PRICE_MARKUP))
            labels = {'economic':'اقتصادی-حجمی','normal':'عادی-حجمی','pro':'پرو- نامحدود حجم'}
            backend_labels = {'economic':'اقتصادی','normal':'عادی','pro':'پرو'}
            order = {
                'id': make_order_id(), 'user_id': uid, 'service': 'V2Ray',
                'v2ray_tier': backend_labels.get(tier, tier),
                'v2ray_tier_display': labels.get(tier, tier),
                'volume': f'{gb}GB', 'duration': '1 ماهه', 'speed': '-',
                'price': final_price, 'price_markup_applied': True,
                'price_markup_rate': PRICE_MARKUP, 'status': 'draft',
                'created_at': datetime.now().isoformat()
            }
            context.user_data['order'] = order
            context.user_data['v2ray_wait_custom'] = False
            context.user_data['awaiting_invoice_confirmation'] = True
            context.user_data['invoice_confirmed'] = False
            tier_line = f"📊 نوع سرویس: {order['v2ray_tier_display']}\n"
            invoice = (
                '🧾 فاکتور سفارش\n\n'
                f"🌐 سرویس: V2Ray ✨\n{tier_line}"
                f"📦 حجم/پلن: {order['volume']} 📦\n"
                f"⏳ مدت: {order['duration']} ⏱️\n"
                f"🚀 سرعت: {order['speed']} ⚡\n"
                f"💰 مبلغ: {money(final_price)} 💳\n\n"
                '🔎 لطفاً فاکتور را بررسی کن.\n\n'
                '✅ اگر مشخصات و مبلغ درست است، فاکتور را تأیید کن.'
            )
            await q.answer()
            return await q.edit_message_text(
                invoice,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton('✅ تأیید فاکتور و ادامه', callback_data='invoiceconfirm:yes')],
                    [InlineKeyboardButton('❌ لغو سفارش', callback_data='invoiceconfirm:no')]
                ])
            )
        return await q.answer('این دکمه شناخته نشد.', show_alert=True)
    if d.startswith('info:'):
        oid = d.split(':', 1)[1]
        o = load_orders().get(oid)

        if not o or str(o.get('user_id')) != str(uid):
            return await q.answer(
                '❌ سرویس پیدا نشد.',
                show_alert=True
            )

        await q.answer("⏳ در حال دریافت اطلاعات...")

        # لینک
        sub_url = o.get("subscription_url")

        if sub_url:
            await q.message.reply_text(
                "🔗 لینک اشتراک:\n\n" + str(sub_url)
            )

        # اطلاعات زنده
        live, live_err = await v2route_live_info(o)

        if live:
            await q.message.reply_text(
                live_info_text(o, live)
            )
        else:
            await q.message.reply_text(
                "⚠️ " + str(live_err)
            )

        # QR
        await send_vynexa_qr(
            context,
            uid,
            sub_url
        )

        # اطلاعات ذخیره‌شده قبلی
        vals = o.get("delivery", [])

        for x in vals:

            if x.get("type") == "photo":
                await q.message.reply_photo(
                    x["value"],
                    caption="@VynexaVPN_bot"
                )

            elif x.get("type") == "document":
                await q.message.reply_document(
                    x["value"]
                )

            elif x.get("type") == "text":
                # لینک تکراری را دوباره نفرست
                value = str(x.get("value", ""))

                if value.startswith(("http://", "https://")):
                    continue

                await q.message.reply_text(value)

        return

    if d.startswith('del:'):
        oid=d.split(':',1)[1]; orders=load_orders(); o=orders.get(oid)
        if not o or str(o.get('user_id'))!=str(uid): return await q.answer('❌ سرویس پیدا نشد.',show_alert=True)
        o['status']='deleted'; orders[oid]=o; save_orders(orders); return await q.answer('🗑 سرویس حذف شد.')
    if d.startswith('bad:'):
        oid = d.split(':', 1)[1]
        orders = load_orders()
        o = orders.get(oid)

        if not o or str(o.get('user_id')) != str(uid):
            return await q.answer(
                '❌ سرویس پیدا نشد.',
                show_alert=True
            )

        context.user_data['waiting_ticket'] = oid
        await q.answer()

        return await q.message.reply_text(
            "🎫 تیکت پشتیبانی" + chr(10) + chr(10) +
            "مشکل سرویس خود را گزارش دهید." + chr(10) +
            "مشکل را همینجا بنویسید:"
        )

    # ===== ADMIN TICKET CALLBACKS =====

    if d.startswith('ticketinfo:'):
        if not is_admin(uid):
            return await q.answer(
                '⛔ فقط مدیر',
                show_alert=True
            )

        oid = d.split(':', 1)[1]
        o = load_orders().get(oid)

        if not o:
            return await q.answer(
                '❌ سرویس پیدا نشد.',
                show_alert=True
            )

        return await q.message.reply_text(
            "📥 اطلاعات سرویس" + chr(10) + chr(10) +
            order_summary(o)
        )

    if d.startswith('ticketview:'):
        if not is_admin(uid):
            return await q.answer(
                '⛔ فقط مدیر',
                show_alert=True
            )

        oid = d.split(':', 1)[1]
        o = load_orders().get(oid)

        if not o:
            return await q.answer(
                '❌ سرویس پیدا نشد.',
                show_alert=True
            )

        ticket = o.get("ticket") or {}
        ticket_text = ticket.get(
            "text",
            "❌ متن تیکت موجود نیست."
        )

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "💬 پاسخ به تیکت",
                callback_data=f"ticketreply:{oid}"
            )]
        ])

        return await q.message.reply_text(
            "🎫 تیکت ثبت شده کاربر" + chr(10) + chr(10) +
            ticket_text,
            reply_markup=markup
        )

    if d.startswith('ticketreply:'):
        if not is_admin(uid):
            return await q.answer(
                '⛔ فقط مدیر',
                show_alert=True
            )

        oid = d.split(':', 1)[1]

        if not load_orders().get(oid):
            return await q.answer(
                '❌ سرویس پیدا نشد.',
                show_alert=True
            )

        context.user_data['admin_ticket_reply'] = oid
        await q.answer()

        return await q.message.reply_text(
            "💬 پاسخ به تیکت" + chr(10) + chr(10) +
            "پاسخ خود را بنویسید:"
        )

    if d.startswith('renewpick:'):
        oid = d.split(':', 1)[1]
        orders = load_orders(); old = orders.get(oid)
        if not old or str(old.get('user_id')) != str(uid):
            return await q.answer('❌ سرویس پیدا نشد.', show_alert=True)
        await q.answer()
        return await show_renewal_confirmation(update, context, old, oid)
    if d.startswith('renewyes:'):
        oid = d.split(':', 1)[1]
        orders = load_orders(); old = orders.get(oid)
        if not old or str(old.get('user_id')) != str(uid):
            return await q.answer('❌ سرویس پیدا نشد.', show_alert=True)
        await q.answer()
        return await create_renewal_order(update, context, oid)
    if d.startswith('renewno:'):
        oid = d.split(':', 1)[1]
        orders = load_orders(); old = orders.get(oid)
        if not old or str(old.get('user_id')) != str(uid):
            return await q.answer('❌ سرویس پیدا نشد.', show_alert=True)
        context.user_data.pop('renew_selected_oid', None)
        try: await q.edit_message_text('❌ تمدید سرویس لغو شد.')
        except Exception: pass
        return await q.answer('تمدید لغو شد.')
    if d.startswith('ref_claim') or d.startswith('ref_refresh') or d.startswith('ref_admin:'):
        return await referral_callback(update, context)
    if d.startswith("dice_allow:"):
        if not is_admin(uid):
            return await q.answer("⛔ فقط مدیر", show_alert=True)

        target_uid = d.split(":", 1)[1]
        users = load_users()
        target = users.setdefault(str(target_uid), {})

        # فعال‌سازی کامل گردونه برای این کاربر
        target["dice_disabled"] = False
        target.pop("dice_blocked", None)
        target["dice_extra_spins"] = int(
            target.get("dice_extra_spins", 0) or 0
        ) + 1

        save_users(users)

        await q.answer("✅ گردونه برای این کاربر دوباره فعال شد.")

        try:
            await context.bot.send_message(
                int(target_uid),
                "🎲 **یک فرصت اضافه برای گردونه شانس داری!**\n\n"
                "مدیر یک نوبت اضافه برایت فعال کرد 💙\n"
                "می‌تونی دوباره از 🎲 گردونه شانس استفاده کنی.",
                parse_mode="Markdown"
            )
        except Exception as e:
            print("DICE USER NOTIFY ERROR:", repr(e))

        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

        return

    if not is_admin(uid): return await q.answer('⛔ فقط مدیر',show_alert=True)
    if d.startswith('payok:'): return await admin_confirm(update,context,True)
    if d.startswith('payno:'): return await admin_confirm(update,context,False)
    if d.startswith('resend:'):
        oid=d.split(':',1)[1]; context.user_data['delivery_order']=oid; await q.answer(); return await q.message.reply_text('📥 اطلاعات جدید را بفرست؛ عکس، فایل یا متن.')
    if d.startswith('sendcfg:'):
        oid=d.split(':',1)[1]; ok=await send_saved_config(context,oid); return await q.answer('✅ برای مشتری ارسال شد.' if ok else '❌ اطلاعاتی برای ارسال نیست.',show_alert=True)
    if d.startswith('walletok:') or d.startswith('walletno:'):
        oid=d.split(':',1)[1]; orders=load_orders(); o=orders.get(oid)
        if not o: return await q.answer('❌ پیدا نشد.',show_alert=True)
        if d.startswith('walletok:'):
            add_wallet(int(o['user_id']),int(o['amount'])); o['status']='wallet_paid'; orders[oid]=o; save_orders(orders)
            await q.edit_message_caption(caption='✅ شارژ کیف پول تأیید شد.\n\n'+f'مبلغ: {money(o["amount"])}')
            await context.bot.send_message(int(o['user_id']),f'✅ شارژ کیف پول شما تأیید شد.\n\n💰 مبلغ: {money(o["amount"])}\n💵 موجودی جدید: {money(wallet_balance(int(o["user_id"]))) }')
        else:
            o['status']='wallet_rejected'; orders[oid]=o; save_orders(orders)
            try: await q.edit_message_caption(caption='❌ شارژ کیف پول رد شد.')
            except Exception: pass
            await context.bot.send_message(int(o['user_id']),'❌ درخواست شارژ کیف پول تأیید نشد.')
        return


async def wallet_receipt_photo(update, context):
    return await photo_handler(update, context)



async def service_expiry_monitor(context):
    orders=load_orders(); changed=False
    now_ts=int(datetime.now().timestamp())
    for oid,o in list(orders.items()):
        if o.get('status') not in ('delivered','paid','confirmed') or not o.get('subscription_url'):
            continue
        try:
            info,err=await v2route_live_info(o)
            if not info: continue
            total=int(info.get('total',0) or 0); remaining=int(info.get('remaining',0) or 0); expire=int(info.get('expire',0) or 0)
            if not total and not expire: continue
            state=o.get('expiry_notice_state',{})
            if not isinstance(state,dict): state={}
            notices=[]
            # 90% of volume consumed
            if total>0 and remaining <= total*0.10 and remaining>0:
                notices.append(('volume90','⚠️ هشدار حجم سرویس\n\n📦 حدود ۹۰٪ حجم سرویس شما مصرف شده است.\n🔄 بهتره قبل از تمام شدن حجم، سرویس را تمدید/تهیه کنید.'))
            elif total>0 and remaining<=0:
                notices.append(('volume_expired','🔴 حجم سرویس شما تمام شده است.\n\n📦 حجم باقی‌مانده: 0 GB\n🔄 برای ادامه استفاده، سرویس را تمدید کنید.'))
            # 90% of time elapsed: duration from order creation, with 30/90 day defaults
            if expire>0:
                duration=str(o.get('duration',''))
                days=90 if '3 ماه' in duration else 30
                start=o.get('created_at')
                try: start_ts=int(datetime.fromisoformat(start).timestamp()) if start else expire-days*86400
                except Exception: start_ts=expire-days*86400
                span=max(1,expire-start_ts)
                elapsed=max(0,now_ts-start_ts)
                if expire<=now_ts:
                    notices.append(('date_expired','🔴 تاریخ سرویس شما به پایان رسیده است.\n\n📅 مدت سرویس تمام شده است.\n🔄 برای ادامه استفاده، سرویس را تمدید کنید.'))
                elif elapsed/span>=0.90:
                    notices.append(('date90','⚠️ هشدار پایان سرویس\n\n📅 حدود ۹۰٪ مدت سرویس شما گذشته است.\n🔄 بهتره قبل از پایان، سرویس را تمدید کنید.'))
            for key,msg in notices:
                if state.get(key): continue
                try:
                    await context.bot.send_message(int(o['user_id']),msg,reply_markup=home(int(o['user_id'])))
                    state[key]=datetime.now().isoformat(); changed=True
                except Exception as e: print('EXPIRY NOTICE ERROR:',oid,repr(e))
            o['expiry_notice_state']=state; orders[oid]=o
        except Exception as e: print('EXPIRY MONITOR ERROR:',oid,repr(e))
    if changed: save_orders(orders)

async def review_job(context):
    orders=load_orders(); changed=False
    for oid,o in orders.items():
        if o.get('status')=='delivered' and not o.get('review_asked'):
            try: due=datetime.fromisoformat(o.get('delivered_at',''))+timedelta(days=3)
            except Exception: continue
            if datetime.now()>=due:
                try:
                    await context.bot.send_message(int(o['user_id']), '💙 سلام!\n\n۳ روز از دریافت سرویس Vynexa-VPN گذشته.\n\n⭐ اگر فرصت داری، تجربه‌ات از سرعت و پایداری سرویس رو برامون بنویس. نظر تو برای ما مهمه ❤️')
                    o['review_asked']=True; changed=True
                except Exception: pass
    if changed: save_orders(orders)


async def ai_status_cmd(update, context):
    uid = update.effective_user.id
    if not is_admin(uid):
        return await update.message.reply_text("⛔ این بخش فقط برای مدیر است.")
    await update.message.reply_text(
        "🤖 وضعیت پاسخ‌گویی Vynexa\n\n"
        "وضعیت: 🟢 فعال\n"
        "حالت: Local AI\n"
        "API: بدون نیاز به API Key\n"
        "پاسخ‌های محلی: بیش از ۱۰۰۰ حالت ترکیبی"
    )



async def expiry_monitor_post_init(application):
    application.create_task(_expiry_monitor_loop(application))


async def _expiry_monitor_loop(application):
    while True:
        try:
            await service_expiry_monitor(application)
        except Exception as e:
            print('EXPIRY LOOP ERROR:',repr(e))
        await asyncio.sleep(7200)





# VYNEXA_TOGGLE_BROADCAST
async def _vynexa_broadcast_toggle(bot, enabled):
    if enabled:
        message = "🎉 خبر خوب، دوست عزیز!\\nربات VynexaVPN دوباره فعاله 💙\\nمی‌تونی از امکاناتش استفاده کنی 🙂"
    else:
        message = "🔴 دوست عزیز VynexaVPN، ربات موقتاً خاموش شده است.\\nبه‌محض فعال‌شدن دوباره بهت اطلاع می‌دیم 💙"
    users = load_users()
    ids = list(users.keys()) if isinstance(users, dict) else list(users) if isinstance(users, list) else []
    sent = 0
    for item in ids:
        try:
            if isinstance(item, dict):
                item = item.get("id", item.get("user_id"))
            await bot.send_message(chat_id=int(item), text=message)
            sent += 1
            await asyncio.sleep(0.04)
        except Exception:
            continue
    print("VYNEXA TOGGLE BROADCAST:", "ON" if enabled else "OFF", sent)
# END VYNEXA_TOGGLE_BROADCAST


async def vynexa_commands_post_init(application):
    await expiry_monitor_post_init(application)
    try:
        from telegram import BotCommand, BotCommandScopeChat
        await application.bot.set_my_commands([
            BotCommand("start", "شروع ربات")
        ])
        aid = admin_id()
        if aid:
            await application.bot.set_my_commands(
                [BotCommand("start", "شروع ربات"),
                 BotCommand("admin", "پنل مدیریت")],
                scope=BotCommandScopeChat(chat_id=int(aid))
            )
    except Exception as e:
        print("COMMAND MENU ERROR:", repr(e))


async def vynexa_referral_link_callback(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    link = f"https://t.me/VynexaVPN_bot?start=ref_{uid}"
    await q.message.reply_text(
        f"🔗 لینک اختصاصی تو:\n{link}\n\n💙 برای دوستات بفرست!",
        disable_web_page_preview=True,
    )
    try:
        aid = admin_id()
        if aid:
            await context.bot.send_message(
                chat_id=aid,
                text=(
                    "🔗 دریافت لینک زیرمجموعه‌گیری\n\n"
                    f"👤 نام: {q.from_user.full_name}\n"
                    f"🆔 آیدی عددی: {uid}\n"
                    f"🔗 لینک: {link}"
                ),
            )
    except Exception as e:
        print("REFERRAL ADMIN REPORT ERROR:", repr(e))


async def vynexa_referral_screen(update, context):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    await update.message.reply_text(
        VYNEXA_REFERRAL_TEXT,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🔗 دریافت لینک اختصاصی",
                callback_data="vynexa_referral_get_link",
            )
        ]]),
    )



# ===== VYNEXA CUSTOM EMOJI PICKER =====

def _emoji_rows_for_path(uid, path):
    """Navigate the same hierarchy as the real inline menu; only /emoji asks confirmation."""
    if not path:
        rows = [
            ['🛒 خرید سرویس', '🔄 تمدید سرویس'],
            ['📦 سرویس‌های من', '🎧 پشتیبانی'],
            ['💰 کیف پول'], ['🌐 پروکسی تلگرام'], ['🎲 گردان شانس'],
            ['👥 زیرمجموعه‌گیری'], ['🤖 سوالات هوش مصنوعی'],
        ]
        if is_admin(uid): rows += [['📢 اطلاعیه', '🤖 ربات روشن/خاموش']]
        return rows, '🏠 منوی اصلی — دکمه‌ای را انتخاب کن:'
    if path == ['🛒 خرید سرویس']:
        return [['🌐 V2Ray'], ['🟢 WireGuard'], ['🔵 OpenVPN'], ['🔙 برگشت']], '🛒 خرید سرویس — نوع سرویس را انتخاب کن:'
    if path == ['🛒 خرید سرویس', '🌐 V2Ray']:
        return [['💚 اقتصادی-حجمی'], ['🔵 عادی-حجمی'], ['🟣 پرو- نامحدود حجم'], ['🧪 تست رایگان'], ['🔙 برگشت']], '🌐 V2Ray — نوع سرویس را انتخاب کن:'
    if path == ['🛒 خرید سرویس', '🌐 V2Ray', '🟣 پرو- نامحدود حجم']:
        return [['👤 تک کاربر'], ['👥 چند کاربر'], ['🔙 برگشت']], '🟣 پرو — تعداد کاربران را انتخاب کن:'
    if path == ['🛒 خرید سرویس', '🌐 V2Ray', '🟣 پرو- نامحدود حجم', '👤 تک کاربر']:
        return [['📅 1 ماهه'], ['📅 2 ماهه'], ['📅 3 ماهه'], ['🔙 برگشت']], '👤 پرو تک‌کاربر — مدت را انتخاب کن:'
    if path == ['🛒 خرید سرویس', '🌐 V2Ray', '💚 اقتصادی-حجمی'] or path == ['🛒 خرید سرویس', '🌐 V2Ray', '🔵 عادی-حجمی']:
        return [['📅 1 ماهه'], ['📅 3 ماهه'], ['🔙 برگشت']], 'V2Ray — مدت را انتخاب کن:'
    if path == ['🔄 تمدید سرویس']:
        return [['📦 سرویس‌های من'], ['🔙 برگشت']], '🔄 تمدید سرویس — ابتدا سرویس‌هایت را باز کن:'
    if path in (['🟢 WireGuard'], ['🔵 OpenVPN']):
        return [['📅 1 ماهه'], ['📅 3 ماهه'], ['🔙 برگشت']], 'نوع سرویس — مرحلهٔ بعد را انتخاب کن:'
    if path and path[-1] == '🔙 برگشت':
        return _emoji_rows_for_path(uid, path[:-1])
    return _emoji_rows_for_path(uid, [])


def _emoji_flatten(rows):
    return [label for row in rows for label in row]


def _emoji_targets_markup(rows):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    out=[]
    for row in rows:
        out.append([InlineKeyboardButton(label, callback_data=f'emoji:target:{_emoji_flatten(rows).index(label)}') for label in row])
    return InlineKeyboardMarkup(out)


def _emoji_confirm_markup():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([[
        InlineKeyboardButton('✅ بله', callback_data='emoji:confirm:yes'),
        InlineKeyboardButton('❌ نه', callback_data='emoji:confirm:no'),
    ], [InlineKeyboardButton('↩️ برگشت به منو', callback_data='emoji:back')]])


async def emoji_picker_start(update, context):
    uid=update.effective_user.id
    if not is_admin(uid):
        return await update.effective_message.reply_text('⛔ این ابزار فقط برای مدیر ربات است.')
    context.user_data['vynexa_emoji_path']=[]
    context.user_data.pop('vynexa_emoji_target',None)
    context.user_data.pop('waiting_custom_emoji',None)
    rows,title=_emoji_rows_for_path(uid,[])
    context.user_data['vynexa_emoji_rows']=rows
    return await update.effective_message.reply_text('🎨 تنظیم ایموجی دکمه‌ها\n\n'+title, reply_markup=_emoji_targets_markup(rows))


async def emoji_picker_callback(update, context):
    q=update.callback_query; uid=q.from_user.id
    if not is_admin(uid): return await q.answer('فقط مدیر ربات دسترسی دارد.',show_alert=True)
    data=(q.data or '').split(':')
    await q.answer()
    path=context.user_data.get('vynexa_emoji_path',[])
    action=data[1] if len(data)>1 else ''
    if action in ('back','targets'):
        context.user_data.pop('waiting_custom_emoji',None)
        if action=='back' and path: path=path[:-1]
        context.user_data['vynexa_emoji_path']=path
        rows,title=_emoji_rows_for_path(uid,path)
        context.user_data['vynexa_emoji_rows']=rows
        return await q.edit_message_text('🎨 تنظیم ایموجی دکمه‌ها\n\n'+title,reply_markup=_emoji_targets_markup(rows))
    if action=='target':
        rows=context.user_data.get('vynexa_emoji_rows')
        if not rows: rows,_=_emoji_rows_for_path(uid,path)
        labels=_emoji_flatten(rows); idx=int(data[2])
        if idx<0 or idx>=len(labels): return await q.answer('انتخاب معتبر نیست.',show_alert=True)
        target=labels[idx]
        if target=='🔙 برگشت':
            path=path[:-1] if path else []
            context.user_data['vynexa_emoji_path']=path
            rows,title=_emoji_rows_for_path(uid,path); context.user_data['vynexa_emoji_rows']=rows
            return await q.edit_message_text('🎨 تنظیم ایموجی دکمه‌ها\n\n'+title,reply_markup=_emoji_targets_markup(rows))
        context.user_data['vynexa_emoji_target']=target
        context.user_data['vynexa_emoji_path_at_target']=list(path)
        context.user_data.pop('waiting_custom_emoji',None)
        return await q.edit_message_text(f'🎯 {target}\n\nمی‌خوای ایموجی همین دکمه رو تغییر بدی؟',reply_markup=_emoji_confirm_markup())
    if action=='confirm':
        choice=data[2] if len(data)>2 else ''
        target=context.user_data.get('vynexa_emoji_target')
        if choice=='yes':
            if not target: return await q.edit_message_text('⚠️ اول دکمه‌ای انتخاب کن.')
            context.user_data['waiting_custom_emoji']=True
            return await q.edit_message_text(f'باشه 💙 ایموجی دلخواهت رو بفرست.\n\nدکمه: {target}\n\nپک و گالری وجود نداره؛ مستقیم خود ایموجی رو بفرست.')
        if choice=='no':
            if not target: path=[]
            else: path=list(context.user_data.get('vynexa_emoji_path_at_target',[]))+[target]
            context.user_data['vynexa_emoji_path']=path
            context.user_data.pop('waiting_custom_emoji',None)
            rows,title=_emoji_rows_for_path(uid,path)
            context.user_data['vynexa_emoji_rows']=rows
            return await q.edit_message_text('🎨 تنظیم ایموجی دکمه‌ها\n\n'+title,reply_markup=_emoji_targets_markup(rows))
    rows,title=_emoji_rows_for_path(uid,path); context.user_data['vynexa_emoji_rows']=rows
    return await q.edit_message_text(title,reply_markup=_emoji_targets_markup(rows))

def main():
    # Prevent two copies of this same new file from polling/responding at once.
    # Older script versions must still be stopped manually once before starting this version.
    global _VYNEXA_INSTANCE_LOCK
    try:
        import fcntl
        _VYNEXA_INSTANCE_LOCK = open(HOME / '.vynexa_rebuilt_v22.lock', 'w')
        fcntl.flock(_VYNEXA_INSTANCE_LOCK.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('VynexaVPN is already running; stop the duplicate process first.')
    except Exception as lock_error:
        print('INSTANCE LOCK WARNING:', repr(lock_error)[:120])
    token=find_token()
    if not token: raise SystemExit('❌ TOKEN پیدا نشد. توکن قبلی در bot_old_backup.py یا config.json موجود نیست.')
    c=load_config(); c.setdefault('bot_enabled',True); c.setdefault('prices',{})
    c = setup_ai_config()
    save_config(c)
    # Normal API requests stay snappy; getUpdates needs a longer read timeout than
    # Telegram's long-poll timeout or it can report false timeouts while online.
    req={'connect_timeout':5.0,'read_timeout':10.0,'write_timeout':10.0,'pool_timeout':3.0,'connection_pool_size':64}
    get_updates_req={'connect_timeout':8.0,'read_timeout':25.0,'write_timeout':10.0,'pool_timeout':5.0,'connection_pool_size':64}
    builder=Application.builder().token(token).post_init(vynexa_commands_post_init).concurrent_updates(32)
    proxy=c.get('bot_proxy')
    builder = builder.request(HTTPXRequest(**req)).get_updates_request(HTTPXRequest(**get_updates_req))
    app=builder.build()
    # VYNEXA_DISCOUNT
    from telegram import Update
    from telegram.ext import TypeHandler

    app.add_handler(MessageHandler(filters.ALL, force_join_gate), group=-1)
    app.add_handler(CallbackQueryHandler(force_join_gate), group=-1)
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, vynexa_webapp_data))

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('admin', admin_cmd))
    app.add_handler(CommandHandler('emoji', emoji_picker_start))
    app.add_handler(CallbackQueryHandler(emoji_picker_callback, pattern=r'^emoji:'))
    app.add_handler(CallbackQueryHandler(join_approval_callback, pattern=r'^(approve_join|decline_join):'))
    app.add_handler(CallbackQueryHandler(ai_faq_callback, pattern=r'^ai_faq:'))
    app.add_handler(CallbackQueryHandler(dice_delete_callback, pattern=r'^dice_delete:'))
    app.add_handler(CallbackQueryHandler(inline_menu_router, pattern=r'^menu:'))
    app.add_handler(CallbackQueryHandler(buy_confirmation_callback, pattern=r'^buyconfirm:'))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(ChatJoinRequestHandler(join_request_handler))
    app.add_handler(ChatMemberHandler(vynexa_channel_member_update, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, photo_handler))
    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.COMMAND, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, vynexa_generic_link_qr),
        group=1
    )

    if app.job_queue:
        app.job_queue.run_repeating(review_job, interval=3600, first=30)

    print('Vynexa-VPN V22 RECONNECT FIX started')
    app.add_handler(MessageHandler(filters.Regex(r"^🎲 گردان شانس$"), vynexa_dice))


    # VYNEXA_AUTO_QR_CLASS_PATCH
    import re as _qr_re
    import io as _qr_io
    import struct as _qr_struct
    import zlib as _qr_zlib
    import qrcode as _qr_lib

    _qr_bot_class = type(app.bot)
    _qr_original_send_message = _qr_bot_class.send_message

    async def _qr_send_message_and_image(self, *args, **kwargs):
        result = await _qr_original_send_message(self, *args, **kwargs)
        try:
            _chat_id = kwargs.get("chat_id", args[0] if args else None)
            _text = kwargs.get("text", args[1] if len(args) > 1 else "")
            _match = _qr_re.search(r"(?i)https?://[^\s<>]+", str(_text or ""))
            if _chat_id is not None and _match:
                _url = _match.group(0).rstrip(".,!?;:)]}»")
                _qr = _qr_lib.QRCode(
                    error_correction=_qr_lib.constants.ERROR_CORRECT_M,
                    box_size=1, border=4
                )
                _qr.add_data(_url)
                _qr.make(fit=True)
                _matrix = _qr.get_matrix()
                _scale = max(4, min(10, 900 // len(_matrix)))
                _width = len(_matrix) * _scale
                _raw = bytearray()
                for _row in _matrix:
                    _line = bytearray([0])
                    for _cell in _row:
                        _v = 0 if _cell else 255
                        _line.extend(bytes((_v, _v, _v)) * _scale)
                    for _ in range(_scale):
                        _raw.extend(_line)

                def _qr_chunk(_kind, _data):
                    return (_qr_struct.pack(">I", len(_data)) + _kind + _data +
                            _qr_struct.pack(">I", _qr_zlib.crc32(_kind + _data) & 0xffffffff))

                _png = (b"\x89PNG\r\n\x1a\n" +
                        _qr_chunk(b"IHDR", _qr_struct.pack(">IIBBBBB", _width, _width, 8, 2, 0, 0, 0)) +
                        _qr_chunk(b"IDAT", _qr_zlib.compress(bytes(_raw))) +
                        _qr_chunk(b"IEND", b""))
                await self.send_photo(
                    chat_id=_chat_id,
                    photo=_qr_io.BytesIO(_png),
                    caption="💙 QR لینک سرویس شما\n" + _url[:900]
                )
        except Exception as _qr_error:
            print("AUTO QR ERROR:", str(_qr_error)[:250])
        return result

    _qr_bot_class.send_message = _qr_send_message_and_image

    app.run_polling(poll_interval=0.0, timeout=10, bootstrap_retries=-1, drop_pending_updates=False, allowed_updates=Update.ALL_TYPES)



# VYNEXA_GENERIC_LINK_QR_FIXED
async def vynexa_generic_link_qr(update, context):
    import re, io, struct, zlib
    import qrcode

    msg = update.effective_message
    if not msg or not msg.text:
        return
    match = re.search(r'(?i)(?:https?://|tg://|www\.)[^\s<>]+', msg.text)
    if not match:
        return

    url = match.group(0).rstrip(".,!?;:)]}»")
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1, border=4
    )
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    scale = max(4, min(10, 900 // len(matrix)))
    width = len(matrix) * scale
    raw = bytearray()

    for row in matrix:
        line = bytearray([0])
        for cell in row:
            v = 0 if cell else 255
            line.extend(bytes((v, v, v)) * scale)
        for _ in range(scale):
            raw.extend(line)

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data +
                struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff))

    png = (b"\x89PNG\r\n\x1a\n" +
           chunk(b"IHDR", struct.pack(">IIBBBBB", width, width, 8, 2, 0, 0, 0)) +
           chunk(b"IDAT", zlib.compress(bytes(raw))) +
           chunk(b"IEND", b""))

    await msg.reply_photo(
        photo=io.BytesIO(png),
        caption="💙 QR لینک شما\n" + url[:900]
    )

# ===== VYNEXA CHANNEL BUTTONS =====
def vynexa_channel_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🛒 خرید سرویس",
                url="https://t.me/VynexaVPN_bot?start=buy"
            ),
            InlineKeyboardButton(
                "🎁 دریافت تست رایگان",
                url="https://t.me/VynexaVPN_bot?start=test"
            )
        ],
        [
            InlineKeyboardButton(
                "🎲 گردونه شانس",
                url="https://t.me/VynexaVPN_bot?start=dice"
            ),
            InlineKeyboardButton(
                "🎧 ارتباط با پشتیبانی",
                url="https://t.me/VynexaVPN_bot?start=support"
            )
        ]
    ])

# ===== VYNEXA_DICE_GAME =====
VYNEXA_DICE_GAME=True

async def vynexa_dice(update, context):
    import random
    import asyncio
    from datetime import datetime

    uid = str(update.effective_user.id)
    users = load_users()
    u = users.setdefault(uid, {})
    if u.get("dice_blocked", False):
        return await update.effective_message.reply_text(
            "⛔ دسترسی شما به گردونه شانس غیرفعال شده است."
        )

    today = datetime.now().strftime("%Y-%m-%d")

    # هر کاربر روزی یک بار؛ سهمیه اضافه با اجازه ادمین
    extra = int(u.get("dice_extra_spins", 0) or 0)

    if u.get("dice_last_date") == today:
        if extra <= 0:
            return await update.effective_message.reply_text(
                "🎲 امروز تاس رو انداختی!\n\n"
                "فردا دوباره شانست رو امتحان کن 💙"
            )
        u["dice_extra_spins"] = extra - 1
        save_users(users)

    dice_msg = await update.effective_message.reply_text("🎲")
    await asyncio.sleep(1.2)

    n = random.randint(1, 6)

    u["dice_last_date"] = today
    u["dice_last_number"] = n
    u["dice_last_time"] = datetime.now().isoformat()

    prizes = {
        1: "🔥 ۱۰٪ تخفیف V2Ray Pro",
        2: "💎 ۱۰٪ تخفیف V2Ray عادی",
        3: "🎁 ۱۰٪ تخفیف V2Ray اقتصادی",
        4: "💰 ۱۰,۰۰۰ تومان اعتبار کیف پول",
        5: "🔐 ۱۰٪ تخفیف OpenVPN",
        6: "⚡ ۱۰٪ تخفیف WireGuard",
    }

    prize = prizes[n]

    # جایزه کیف پول
    if n == 4:
        u["wallet"] = int(u.get("wallet", 0) or 0) + 10000
        u["dice_reward"] = "10000_wallet"
        u["dice_reward_text"] = prize
        save_users(users)

        text = (
            f"🎲 تاس روی **{n}** افتاد!\n\n"
            f"{prize}\n\n"
            "✅ اعتبار به کیف پولت اضافه شد."
        )

    # کدهای تخفیف
    else:
        reward_data = {
            1: (10, "pro"),
            2: (10, "normal"),
            3: (10, "economic"),
            5: (10, "openvpn"),
            6: (10, "wireguard"),
        }

        percent, tier = reward_data[n]

        code = f"VX{random.randint(100000, 999999)}"

        u.setdefault("dice_discount_rewards", []).append({
            "code": code,
            "percent": percent,
            "tier": tier,
            "used": False,
            "created_at": datetime.now().isoformat()
        })

        u["dice_reward"] = code
        u["dice_reward_text"] = prize
        save_users(users)

        text = (
            f"🎲 تاس روی **{n}** افتاد!\n\n"
            f"{prize}\n\n"
            "🎟️ کد اختصاصی:\n"
            f"`{code}`"
        )

    # گزارش کامل برای ادمین
    try:
        aid = admin_id()
        if aid:
            uname = update.effective_user.username
            first = update.effective_user.first_name or "بدون نام"

            admin_text = (
                "🎲 **گزارش گردونه شانس**\n\n"
                f"👤 نام: {first}\n"
                f"🔹 Username: @{uname}" if uname else
                f"🎲 **گزارش گردونه شانس**\n\n👤 نام: {first}"
            )

            admin_text += (
                f"\n🆔 آیدی: `{uid}`"
                f"\n🎲 نتیجه: {n}"
                f"\n🎁 جایزه: {prize}"
            )

            if n in (1, 2, 5, 6):
                admin_text += f"\n🎟️ کد: `{code}`"

            if extra > 0:
                admin_text += f"\n♻️ سهمیه اضافه باقی‌مانده: {extra}"

            markup = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "🔄 اجازه استفاده دوباره",
                    callback_data=f"dice_allow:{uid}"
                ),
                InlineKeyboardButton(
                    "🗑 حذف گردونه",
                    callback_data=f"dice_delete:{uid}"
                )
            ]])

            await context.bot.send_message(
                aid,
                admin_text,
                parse_mode="Markdown",
                reply_markup=markup
            )
    except Exception as e:
        print("DICE ADMIN REPORT ERROR:", repr(e))

    await dice_msg.edit_text(text, parse_mode="Markdown")


async def dice_admin_panel(update, context):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("⛔ فقط مدیر.")

    users = load_users()
    rows = []
    found = False

    for uid, u in users.items():
        if not isinstance(u, dict):
            continue

        if not u.get("dice_last_date"):
            continue

        found = True
        last_date = u.get("dice_last_date", "-")
        number = u.get("dice_last_number", "-")
        reward = u.get("dice_reward_text", "-")
        extra = int(u.get("dice_extra_spins", 0) or 0)

        rows.append([
            InlineKeyboardButton(
                f"🔄 اجازه دوباره | {uid}",
                callback_data=f"dice_allow:{uid}"
            ),
            InlineKeyboardButton(
                "🗑 حذف گردونه",
                callback_data=f"dice_delete:{uid}"
            )
        ])

        await update.message.reply_text(
            "🎲 **گردونه شانس**\n\n"
            f"👤 آیدی: `{uid}`\n"
            f"📅 آخرین استفاده: {last_date}\n"
            f"🎲 عدد: {number}\n"
            f"🎁 جایزه: {reward}\n"
            f"♻️ سهمیه اضافه: {extra}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([rows[-1]])
        )

    if not found:
        await update.message.reply_text("🎲 هنوز هیچ کاربری از گردونه استفاده نکرده است.")

    return


async def vynexa_webapp_data(update, context):
    try:
        data=json.loads(update.effective_message.web_app_data.data)
        if data.get("action")!="buy":
            return await update.effective_message.reply_text("❌ درخواست نامعتبر است.")
        service=str(data.get("service","")).strip()
        prices=load_config().get("prices",{})
        key=next((k for k in prices if str(k).strip().lower()==service.lower()),None)
        if key is None:
            return await update.effective_message.reply_text("❌ این سرویس فعال نیست.")
        context.user_data.clear()
        return await choose_vpn(update,context,key)
    except Exception as e:
        print("MINI APP ERROR:",repr(e))
        return await update.effective_message.reply_text("❌ اتصال Mini App با خطا مواجه شد.")

if __name__ == "__main__":
    main()
