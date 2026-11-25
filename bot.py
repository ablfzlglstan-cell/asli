# -*- coding: utf-8 -*-
"""
Her Self Builder  |  single-file, Railway-ready
  * ربات سازنده (Bot API خام => دکمه‌های رنگی) + سلف‌های درون‌پروسه‌ای (pyrogram)
  * سشن‌ها با AES-256-GCM + scrypt رمزنگاری می‌شوند و روی دیسک فقط به‌صورت رمز ذخیره می‌شوند
ENV لازم:  BOT_TOKEN  API_ID  API_HASH
ENV اختیاری: OWNERS  CHANNEL  SUPPORT  DATA_DIR  ENC_KEY
"""
import os, sys, json, time, html, copy, base64, asyncio, logging, random, re, secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiohttp
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from pyrogram import Client, filters, errors
from pyrogram.enums import ChatAction, ChatMemberStatus, ChatType, ParseMode
from pyrogram.handlers import MessageHandler
from pyrogram.raw import functions as rf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("pyrogram").setLevel(logging.WARNING)
log = logging.getLogger("herself")

# ============================ Config ============================
def env(k, d=""):
    return os.environ.get(k, d).strip()

BOT_TOKEN = env("BOT_TOKEN","9139271979:AAFoiKgX9GB12MBzjfSwJfyQ9gAoVLEfcOk")
API_ID = int(env("API_ID", "21991530") or 0)
API_HASH = env("API_HASH","6fedb4494836743356f1624c1e6377ae")
ENV_OWNERS = {int(x) for x in re.findall(r"\d+", env("OWNERS", "8806549778"))}
CHANNEL = env("CHANNEL", "Her_Team").lstrip("@")
SUPPORT = env("SUPPORT","Error404url").lstrip("@")
DATA = Path(env("DATA_DIR", "data"))
TZ = timezone(timedelta(hours=3, minutes=30))
if __name__ == "__main__" and not (BOT_TOKEN and API_ID and API_HASH):
    sys.exit("❌ متغیرهای BOT_TOKEN و API_ID و API_HASH باید در Railway (Variables) تنظیم شوند.")
(DATA / "sessions").mkdir(parents=True, exist_ok=True)

def now():
    return int(time.time())

def h(s):
    return html.escape(str(s), quote=False)

# ============================ Storage ===========================
class JStore:
    _all = []

    def __init__(self, name, default):
        self.path = DATA / name
        self.data = default
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text("utf-8"))
            except Exception:
                self.path.rename(self.path.with_suffix(f".bad{now()}"))
        self.dirty = False
        JStore._all.append(self)

    def mark(self):
        self.dirty = True

    def flush(self):
        if not self.dirty:
            return
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), "utf-8")
        os.replace(tmp, self.path)
        self.dirty = False

async def flusher():
    while True:
        await asyncio.sleep(3)
        for s in JStore._all:
            try:
                s.flush()
            except Exception as e:
                log.error("flush failed: %s", e)

PANEL_DEFAULT = {
    "profile":   {"t": "👤 پروفایل / ساعت", "s": "primary", "on": True},
    "fmt":       {"t": "✍️ فرمت متن", "s": "primary", "on": True},
    "lists":     {"t": "❤️ دوست / دشمن / سکوت", "s": "primary", "on": True},
    "group":     {"t": "👥 گروه", "s": "primary", "on": True},
    "secretary": {"t": "🤫 منشی و AFK", "s": "success", "on": True},
    "react":     {"t": "🔔 ری‌اکشن خودکار", "s": "success", "on": True},
    "reply":     {"t": "💬 پاسخ خودکار", "s": "primary", "on": True},
    "tools":     {"t": "🛠 ابزار", "s": "primary", "on": True},
    "action":    {"t": "⌨️ اکشن", "s": "success", "on": True},
    "system":    {"t": "📊 سیستم و اطلاعات", "s": "success", "on": True},
    "fun":       {"t": "🎲 سرگرمی", "s": "primary", "on": True},
    "health":    {"t": "🛡 سلامت اکانت", "s": "primary", "on": True},
}
DEFAULT_ENEMY = [
    "فعلاً وقتم برای این بحث نیست 😌",
    "حرفات رو شنیدم، ولی نظرم عوض نشد.",
    "با آرامش جواب می‌دم: نه 🌿",
    "اگه حرف حسابی داری بگو، وگرنه شب خوش 🌙",
    "ممنون که وقت گذاشتی؛ من سرگرم کارهای مهم‌ترم.",
    "هر کی هرچی گفت، من همچنان آرومم 🍃",
    "با ادب باش تا با ادب جواب بگیری.",
    "این‌جا خبری از دعوا نیست؛ یه چایی بخور 🍵",
    "پیامت ثبت شد و رفت تو صف انتظار 📨",
    "بذار این گفتگو رو یه وقت دیگه که حوصله دارم ادامه بدیم.",
]
BAD_TOKENS = {"کیر", "کس", "کون", "ننه", "جنده", "کیری", "کونی", "گا", "fuck", "shit", "bitch"}
BAD_SUBSTR = ["کصکش", "کسکش", "مادرجنده", "حرومزاده", "گاییدم", "کیرم", "کونی", "پدرسگ", "fuck"]

CFG_DEFAULT = {
    "bot_on": True, "force_join": True, "channel": CHANNEL,
    "cost": 30, "days": 30, "ref_reward": 5, "daily": 1,
    "support": SUPPORT,
    "buy_text": "💎 برای خرید الماس مبلغ را واریز کنید و رسید را با دکمه زیر ارسال کنید.",
    "help_text": "📖 بعد از فعالسازی، در Saved Messages کلمهٔ <b>پنل</b> را بفرستید تا پنل دکمه‌ای باز شود.",
    "menu_photo": "", "panel_photo": "",
    "panel": copy.deepcopy(PANEL_DEFAULT), "panel_order": list(PANEL_DEFAULT),
    "links": [], "admins": [], "owners": [], "bad_words": [], "enemy_texts": [],
}
cfg_store = JStore("config.json", {})
CFG = cfg_store.data
for _k, _v in CFG_DEFAULT.items():
    CFG.setdefault(_k, copy.deepcopy(_v))
for _k, _v in PANEL_DEFAULT.items():
    CFG["panel"].setdefault(_k, copy.deepcopy(_v))
    if _k not in CFG["panel_order"]:
        CFG["panel_order"].append(_k)
users_store = JStore("users.json", {})
USERS = users_store.data
selfs_store = JStore("selfs.json", {})
SELFS = selfs_store.data

def is_owner(u):
    return u in ENV_OWNERS or u in CFG["owners"]

def is_admin(u):
    return is_owner(u) or u in CFG["admins"]

def has_bad_word(text):
    low = text.lower()
    toks = set(re.findall(r"[\w\u0600-\u06FF]+", low))
    if toks & BAD_TOKENS:
        return True
    return any(w in low for w in BAD_SUBSTR + [w.lower() for w in CFG["bad_words"]])

# ============================ Vault (AES-256-GCM) ===============
class Vault:
    MAGIC = b"HS1"

    def __init__(self):
        salt_p, key_p = DATA / ".salt", DATA / ".enc_key"
        if not salt_p.exists():
            salt_p.write_bytes(os.urandom(16))
        self.salt = salt_p.read_bytes()
        secret = env("ENC_KEY")
        self.from_env = bool(secret)
        if not secret:
            if not key_p.exists():
                key_p.write_text(secrets.token_urlsafe(48))
                os.chmod(key_p, 0o600)
            secret = key_p.read_text().strip()
        key = Scrypt(salt=self.salt, length=32, n=2 ** 15, r=8, p=1).derive(secret.encode())
        self.aes = AESGCM(key)

    def _p(self, uid):
        return DATA / "sessions" / f"{uid}.bin"

    def exists(self, uid):
        return self._p(uid).exists()

    def put(self, uid, obj):
        nonce = os.urandom(12)
        ct = self.aes.encrypt(nonce, json.dumps(obj).encode(), str(uid).encode())
        p = self._p(uid)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(self.MAGIC + nonce + ct)
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)

    def get(self, uid):
        raw = self._p(uid).read_bytes()
        if raw[:3] != self.MAGIC:
            raise ValueError("bad vault blob")
        return json.loads(self.aes.decrypt(raw[3:15], raw[15:], str(uid).encode()))

    def delete(self, uid):
        p = self._p(uid)
        if p.exists():
            size = p.stat().st_size
            p.write_bytes(os.urandom(size))   # بازنویسی قبل از حذف
            p.unlink()

    def count(self):
        return len(list((DATA / "sessions").glob("*.bin")))

# ============================ Bot API (raw) =====================
class TgError(Exception):
    def __init__(self, d):
        self.desc = d.get("description", "")
        self.code = d.get("error_code")
        super().__init__(self.desc)

class BotAPI:
    def __init__(self, token):
        self.base = f"https://api.telegram.org/bot{token}/"
        self.sess = None

    async def call(self, method, **kw):
        if self.sess is None:
            self.sess = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90))
        kw = {k: v for k, v in kw.items() if v is not None}
        d = {}
        for _ in range(3):
            async with self.sess.post(self.base + method, json=kw) as r:
                d = await r.json()
            if d.get("ok"):
                return d["result"]
            if d.get("error_code") == 429:
                await asyncio.sleep(d.get("parameters", {}).get("retry_after", 1) + 1)
                continue
            raise TgError(d)
        raise TgError(d)

bot = BotAPI(BOT_TOKEN or "0:x")
BOT = {"id": 0, "username": ""}

# ============================ Keyboards =========================
def B(text, data=None, style=None, url=None, **kw):
    d = {"text": text}
    if data is not None:
        d["callback_data"] = data
    if url:
        d["url"] = url
    if style:
        d["style"] = style
    d.update(kw)
    return d

def IK(*rows):
    return {"inline_keyboard": [list(r) for r in rows if r]}

def RK(*rows):
    return {"keyboard": [list(r) for r in rows if r], "resize_keyboard": True, "is_persistent": True}

STYLES = ["primary", "success", "danger", None]
STYLE_NAME = {"primary": "🔵 آبی", "success": "🟢 سبز", "danger": "🔴 قرمز", None: "⚪️ پیش‌فرض"}
def ok_style(on):
    return "success" if on else None

def onoff(v):
    return "روشن ✅" if v else "خاموش ❌"

async def send(chat, text, kb=None, photo=None):
    if photo:
        try:
            return await bot.call("sendPhoto", chat_id=chat, photo=photo, caption=text,
                                  parse_mode="HTML", reply_markup=kb)
        except TgError as e:
            log.warning("sendPhoto failed: %s", e)
    return await bot.call("sendMessage", chat_id=chat, text=text, parse_mode="HTML",
                          reply_markup=kb, link_preview_options={"is_disabled": True})

async def safe_send(chat, text, kb=None):
    try:
        return await send(chat, text, kb)
    except Exception as e:
        log.info("safe_send %s failed: %s", chat, e)

def fmt_remaining(ts):
    left = ts - now()
    if left <= 0:
        return "منقضی شده"
    d, rem = divmod(left, 86400)
    return f"{d} روز و {rem // 3600} ساعت"

# ============================ Self (userbot) ====================
SELF_DEFAULT = {
    "clock": False, "clock_base": "", "font": 0, "fmt": "none",
    "enemy": [], "friend": [], "mute": [], "enemy_on": True, "enemy_texts": [],
    "secretary": False, "secretary_text": "سلام! فعلاً در دسترس نیستم، به‌محض آنلاین شدن جواب می‌دم 🌿",
    "afk": False, "afk_text": "الان آفلاینم و در اولین فرصت پیام‌هات رو می‌خونم 🌙", "afk_since": 0,
    "react_on": False, "react_list": False, "react_users": [], "emoji": "❤️",
    "autoreply_on": False, "replies": {},
    "welcome_on": False, "welcome_text": "سلام {name} 🌸 به گروه خوش اومدی!",
    "tagalert": False, "typing": False, "action": "typing", "online": "auto",
}
FMT = {"none": "بدون فرمت", "bold": "بولد", "italic": "ایتالیک", "mono": "مونو",
       "spoiler": "اسپویلر", "strike": "خط‌خورده", "underline": "زیرخط", "quote": "نقل‌قول"}
FMT_TAG = {"bold": "b", "italic": "i", "mono": "code", "spoiler": "spoiler",
           "strike": "s", "underline": "u", "quote": "blockquote"}
EMOJIS = ["❤️", "👍", "🔥", "🎉", "😁", "👏", "🤩", "🙏"]
ACTIONS = {"typing": ("⌨️ تایپ", ChatAction.TYPING), "playing": ("🎮 بازی", ChatAction.PLAYING),
           "voice": ("🎙 ضبط ویس", ChatAction.RECORD_AUDIO), "photo": ("📷 ارسال عکس", ChatAction.UPLOAD_PHOTO)}
DICE = {"d1": "🎲", "d2": "🎯", "d3": "🏀", "d4": "⚽", "d5": "🎰", "d6": "🎳"}
TOGGLES = {"enemy_on", "secretary", "afk", "react_on", "react_list", "autoreply_on",
           "welcome_on", "tagalert", "typing"}

def _digits(base):
    return {ord(str(i)): chr(base + i) for i in range(10)}
FONTS = [{}, _digits(0x1D7EC), _digits(0x1D7F6), _digits(0x1D7D8), _digits(0x06F0)]
FONT_NAMES = ["ساده 12:34", "𝟭𝟮:𝟯𝟰 بولد", "𝟷𝟸:𝟹𝟺 مونو", "𝟙𝟚:𝟛𝟜 توخالی", "۱۲:۳۴ فارسی"]
_D = "0-9\u06F0-\u06F9\U0001D7D8-\U0001D7FF"
TIME_RE = re.compile(rf"\s*[{_D}]{{1,2}}:[{_D}]{{2}}\s*$")

def stylize(t, i):
    return t.translate(FONTS[i % len(FONTS)])

def SC(uid):
    c = SELFS[str(uid)].setdefault("cfg", {})
    for k, v in SELF_DEFAULT.items():
        c.setdefault(k, copy.deepcopy(v))
    return c

RUN = {}
CMD_HELP = ("<b>دستورات (ریپلای یا داخل پی‌وی)</b>\n"
            "<code>.setenemy</code> / <code>.delenemy</code>\n"
            "<code>.setlove</code> / <code>.dellove</code>\n"
            "<code>.mute</code> / <code>.unmute</code>\n"
            "<code>.react</code> / <code>.unreact</code>\n"
            "<code>.save</code> ذخیره پیام ریپلای‌شده\n"
            "<code>.id</code> | <code>.ping</code> | <code>.dice</code>")

def apply_input(uid, kind, txt):
    c = SC(uid)
    txt = txt.strip()
    if not txt or len(txt) > 500:
        return False, "❌ متن خالی یا خیلی طولانی است"
    if kind in ("secretary_text", "afk_text", "welcome_text"):
        c[kind] = txt
    elif kind == "enemy_add":
        if has_bad_word(txt):
            return False, "⛔ متن شامل الفاظ نامناسب است (برای امنیت اکانت مجاز نیست)"
        if len(c["enemy_texts"]) >= 30:
            return False, "❌ حداکثر ۳۰ متن"
        c["enemy_texts"].append(txt)
    elif kind == "reply_add":
        m = re.match(r"^(.+?)\s*[:|]\s*(.+)$", txt, re.S)
        if not m:
            return False, "❌ فرمت: سوال:جواب"
        if len(c["replies"]) >= 40:
            return False, "❌ حداکثر ۴۰ مورد"
        c["replies"][m.group(1).strip().lower()] = m.group(2).strip()
    else:
        return False, "❌ نامعتبر"
    selfs_store.mark()
    return True, "✅ ذخیره شد"

class SelfRunner:
    def __init__(self, uid, session):
        self.uid = uid
        self.client = Client(f"s{uid}", api_id=API_ID, api_hash=API_HASH, session_string=session,
                             in_memory=True, sleep_threshold=20)
        self.me = None
        self.pending = None
        self.sent = set()
        self.cd = {}
        self.t0 = time.time()
        self.tasks = []
        self.clock_last = None

    @property
    def cfg(self):
        return SC(self.uid)

    # ---------- lifecycle ----------
    async def start(self):
        c = self.client
        c.add_handler(MessageHandler(self.h_out, filters.me & ~filters.service), group=0)
        c.add_handler(MessageHandler(self.h_in, filters.private & ~filters.me & ~filters.bot & ~filters.service), group=1)
        c.add_handler(MessageHandler(self.h_tag, filters.group & filters.mentioned & ~filters.me), group=2)
        c.add_handler(MessageHandler(self.h_join, filters.new_chat_members & filters.group), group=3)
        await c.start()
        self.me = await c.get_me()
        SELFS[str(self.uid)]["name"] = self.me.first_name or ""
        selfs_store.mark()
        self.tasks = [asyncio.create_task(self.clock_loop()), asyncio.create_task(self.online_loop())]

    async def stop(self):
        for t in self.tasks:
            t.cancel()
        try:
            await self.client.stop()
        except Exception:
            pass

    # ---------- helpers ----------
    def cool(self, kind, uid, secs):
        k, t = (kind, uid), time.time()
        if t - self.cd.get(k, 0) < secs:
            return False
        self.cd[k] = t
        if len(self.cd) > 2000:
            self.cd = {a: b for a, b in self.cd.items() if t - b < 3600}
        return True

    def remember(self, text):
        if len(self.sent) > 300:
            self.sent.clear()
        self.sent.add(text)

    async def done(self, m, text):
        try:
            await m.edit_text(text)
        except Exception:
            pass
        asyncio.create_task(self._del_later(m, 3))

    @staticmethod
    async def _del_later(m, s):
        await asyncio.sleep(s)
        try:
            await m.delete()
        except Exception:
            pass

    async def guard(self, coro):
        try:
            return await coro
        except errors.FloodWait as e:
            await asyncio.sleep(min(e.value, 60))
        except Exception as e:
            log.debug("self %s: %s", self.uid, e)

    # ---------- background loops ----------
    async def apply_clock(self, force=False):
        c = self.cfg
        t = datetime.now(TZ).strftime("%H:%M")
        if not force and t == self.clock_last:
            return
        name = f"{c['clock_base'][:48]} {stylize(t, c['font'])}".strip()
        await self.client.update_profile(first_name=name)
        self.clock_last = t

    async def clock_loop(self):
        while True:
            await asyncio.sleep(max(1, 61 - datetime.now(TZ).second))
            if self.cfg["clock"]:
                await self.guard(self.apply_clock())

    async def set_clock(self, on):
        c = self.cfg
        me = await self.client.get_me()
        if on:
            c["clock_base"] = TIME_RE.sub("", me.first_name or "").strip() or "Me"
            c["clock"] = True
            await self.apply_clock(force=True)
            msg = "⏰ ساعت نام فعال شد"
        else:
            c["clock"] = False
            if c["clock_base"]:
                await self.client.update_profile(first_name=c["clock_base"])
            msg = "⏰ ساعت خاموش و نام برگردانده شد"
        selfs_store.mark()
        return msg

    async def online_loop(self):
        while True:
            mode = self.cfg["online"]
            if mode in ("online", "offline"):
                await self.guard(self.client.invoke(rf.account.UpdateStatus(offline=(mode == "offline"))))
            await asyncio.sleep(45)

    # ---------- panel ----------
    async def open_panel(self, m):
        try:
            res = await self.client.get_inline_bot_results(BOT["username"], "panel")
            await self.client.send_inline_bot_result(m.chat.id, res.query_id, res.results[0].id)
            await m.delete()
        except Exception as e:
            log.warning("open_panel %s: %s", self.uid, e)
            await self.done(m, "❌ پنل باز نشد (Inline ربات در BotFather فعال است؟)")

    async def delete_panels(self):
        ids = []
        async for msg in self.client.get_chat_history("me", limit=20):
            if msg.via_bot and msg.via_bot.id == BOT["id"]:
                ids.append(msg.id)
        if ids:
            await self.client.delete_messages("me", ids)

    async def spambot(self):
        self.remember("/start")
        await self.client.send_message("SpamBot", "/start")
        await asyncio.sleep(4)
        async for msg in self.client.get_chat_history("SpamBot", limit=1):
            return "🛡 " + (msg.text or "—")[:300]
        return "پاسخی نیامد"

    async def sessions(self):
        r = await self.client.invoke(rf.account.GetAuthorizations())
        lines = [f"• {a.device_model} / {a.platform} / {a.country}" + (" (این سلف)" if a.current else "")
                 for a in r.authorizations[:8]]
        return f"🔐 {len(r.authorizations)} نشست فعال:\n" + "\n".join(lines)

    # ---------- outgoing ----------
    async def h_out(self, c, m):
        if m.via_bot or not m.text or m.text in self.sent:
            return
        txt, cfg = m.text, self.cfg
        if m.chat.id == self.me.id:
            if self.pending and not txt.startswith("."):
                p, self.pending = self.pending, None
                if time.time() - p["t"] < 300:
                    ok, msg = apply_input(self.uid, p["kind"], txt)
                    await self.done(m, msg)
                    await refresh_panel(self.uid, p["inline"], p["route"])
                    return
            if txt.strip().lower() in ("پنل", "panel", "منو"):
                return await self.open_panel(m)
        if txt.startswith("."):
            return await self.command(m)
        if cfg["fmt"] != "none" and m.chat.id != self.me.id and not m.entities:
            tag = FMT_TAG[cfg["fmt"]]
            await self.guard(m.edit_text(f"<{tag}>{h(txt)}</{tag}>", parse_mode=ParseMode.HTML))

    def target(self, m, arg):
        if m.reply_to_message and m.reply_to_message.from_user:
            return m.reply_to_message.from_user.id
        if arg.strip().lstrip("-").isdigit():
            return int(arg.strip())
        if m.chat.type == ChatType.PRIVATE:
            return m.chat.id
        return None

    async def command(self, m):
        parts = m.text[1:].split(None, 1)
        if not parts:
            return
        name, arg = parts[0].lower(), (parts[1] if len(parts) > 1 else "")
        c = self.cfg
        lists = {"setenemy": ("enemy", True), "delenemy": ("enemy", False),
                 "setlove": ("friend", True), "setfriend": ("friend", True),
                 "dellove": ("friend", False), "delfriend": ("friend", False),
                 "mute": ("mute", True), "unmute": ("mute", False),
                 "react": ("react_users", True), "unreact": ("react_users", False)}
        if name in lists:
            key, add = lists[name]
            t = self.target(m, arg)
            if not t or t == self.me.id:
                return await self.done(m, "❌ کاربر مشخص نیست (ریپلای کنید)")
            s = str(t)
            if add and s not in c[key]:
                c[key].append(s)
            if not add and s in c[key]:
                c[key].remove(s)
            if add and key == "enemy" and s in c["friend"]:
                c["friend"].remove(s)
            selfs_store.mark()
            return await self.done(m, "✅ انجام شد")
        if name == "ping":
            t0 = time.time()
            await self.client.get_me()
            return await self.done(m, f"🏓 {int((time.time() - t0) * 1000)}ms")
        if name == "id":
            r = m.reply_to_message
            return await self.done(m, f"🆔 چت: {m.chat.id}" + (f" | کاربر: {r.from_user.id}" if r and r.from_user else ""))
        if name == "save" and m.reply_to_message:
            try:
                await m.reply_to_message.forward("me")
            except Exception:
                await m.reply_to_message.copy("me")
            return await self.done(m, "💾 ذخیره شد")
        if name in ("dice", "slot", "dart", "ball"):
            emo = {"dice": "🎲", "slot": "🎰", "dart": "🎯", "ball": "🏀"}[name]
            await m.delete()
            return await self.client.send_dice(m.chat.id, emo)
        if name in ("help", "راهنما"):
            return await self.done(m, "برای دستورات پنل را باز کنید")

    # ---------- incoming ----------
    async def h_in(self, c, m):
        if not m.from_user:
            return
        cfg, uid = self.cfg, m.from_user.id
        key = str(uid)
        if key in cfg["mute"]:
            return await self.guard(m.delete())
        if cfg["typing"]:
            await self.guard(self.client.send_chat_action(m.chat.id, ACTIONS[cfg["action"]][1]))
        if cfg["react_on"] and (not cfg["react_list"] or key in cfg["react_users"]):
            await self.guard(self.client.send_reaction(m.chat.id, m.id, cfg["emoji"]))
        if key in cfg["enemy"] and cfg["enemy_on"]:
            if self.cool("e", uid, 25):
                t = random.choice(cfg["enemy_texts"] or CFG.get("enemy_texts") or DEFAULT_ENEMY)
                self.remember(t)
                await self.guard(m.reply_text(t))
            return
        if key in cfg["friend"]:
            return
        text = (m.text or "").lower().strip()
        if cfg["autoreply_on"] and text:
            for q, a in cfg["replies"].items():
                if q in text:
                    if self.cool("r" + q, uid, 30):
                        self.remember(a)
                        await self.guard(m.reply_text(a))
                    return
        if cfg["afk"] and self.cool("a", uid, 3600):
            mins = max(1, (now() - cfg["afk_since"]) // 60)
            t = f"{cfg['afk_text']}\n⏱ {mins} دقیقه است آفلاینم"
            self.remember(t)
            await self.guard(m.reply_text(t))
        elif cfg["secretary"] and self.cool("s", uid, 21600):
            self.remember(cfg["secretary_text"])
            await self.guard(m.reply_text(cfg["secretary_text"]))

    async def h_tag(self, c, m):
        if not self.cfg["tagalert"] or not self.cool("t", m.chat.id, 20):
            return
        who = m.from_user.first_name if m.from_user else "—"
        text = f"🔔 تگ شدید در «{m.chat.title}»\n👤 {who}\n💬 {(m.text or m.caption or '')[:200]}\n{m.link or ''}"
        self.remember(text)
        await self.guard(self.client.send_message("me", text))

    async def h_join(self, c, m):
        if not self.cfg["welcome_on"] or not m.new_chat_members or not self.cool("w", m.chat.id, 10):
            return
        try:
            mem = await c.get_chat_member(m.chat.id, "me")
            if mem.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                return
        except Exception:
            return
        names = "، ".join(u.first_name for u in m.new_chat_members if not u.is_bot)
        if names:
            t = self.cfg["welcome_text"].replace("{name}", names)
            self.remember(t)
            await self.guard(c.send_message(m.chat.id, t))

# ============================ Panel rendering ===================
def toggle_btn(label, key, route, c):
    return B(f"{label}: {onoff(c[key])}", f"p:t:{key}:{route}", ok_style(c[key]))

def grid(btns, n=2):
    return [btns[i:i + n] for i in range(0, len(btns), n)]

def render(uid, route, note=""):
    c, meta = SC(uid), SELFS[str(uid)]
    foot = [[B("⬅️ برگشت", "p:set", "primary"), B("🏠 صفحه اول", "p:home", "primary")],
            [B("❌ بستن پنل", "p:close", "danger")]]
    nt = f"\n\n<i>{h(note[:380])}</i>" if note else ""
    if route == "home":
        t = (f"✨ <b>پنل سلف</b>\n👤 {h(meta.get('name', ''))}\n"
             f"⏳ اشتراک: {fmt_remaining(meta['expire'])}")
        rows = [[B("👤 حساب کاربری", "p:acc", "primary"), B("⚙️ تنظیمات سلف", "p:set", "primary")],
                [B("🌐 مدیریت آنلاین سلف", "p:onl", "success")]]
        rows += [[B(l["text"], url=l["url"], style=l.get("s"))] for l in CFG["links"]]
        rows.append([B("❌ بستن پنل", "p:close", "danger")])
        return t + nt, IK(*rows)
    if route == "set":
        btns = [B(CFG["panel"][k]["t"], f"p:c:{k}", CFG["panel"][k]["s"])
                for k in CFG["panel_order"] if k in CFG["panel"] and CFG["panel"][k]["on"]]
        rows = grid(btns) + [[B("🌐 مدیریت آنلاین سلف", "p:onl", "success")],
                             [B("🏠 صفحه اول", "p:home", "primary")], [B("❌ بستن پنل", "p:close", "danger")]]
        return "⚙️ <b>تنظیمات سلف</b>\nیک بخش را انتخاب کنید 👇" + nt, IK(*rows)
    if route == "acc":
        t = (f"👤 <b>حساب کاربری</b>\n🆔 <code>{uid}</code>\n📱 {h(meta.get('phone', '—'))}\n"
             f"⏳ اشتراک: {fmt_remaining(meta['expire'])}\n🔐 سشن: رمزنگاری‌شده (AES-256)")
        return t + nt, IK([B("🏠 صفحه اول", "p:home", "primary")], [B("❌ بستن پنل", "p:close", "danger")])
    if route == "onl":
        cur = c["online"]
        names = {"online": "🟢 آنلاین دائم", "offline": "⚫️ آفلاین دائم", "auto": "🔄 خودکار"}
        btns = [B(("✅ " if k == cur else "") + v, f"p:v:online:{k}:onl", "success" if k == cur else "primary")
                for k, v in names.items()]
        return f"🌐 <b>مدیریت آنلاین سلف</b>\nوضعیت فعلی: {names[cur]}" + nt, IK(btns, [B("🏠 صفحه اول", "p:home", "primary")], [B("❌ بستن پنل", "p:close", "danger")])
    if route in ("confirm_reset", "c:confirm_reset"):
        return "⚠️ همهٔ تنظیمات سلف به حالت اول برمی‌گردد. مطمئنید؟", IK(
            [B("✅ بله، ریست شود", "p:x:resetcfg:set", "danger"), B("❌ خیر", "p:c:tools", "primary")])
    key = route.split(":", 1)[1] if route.startswith("c:") else ""
    rows, t = [], ""
    if key == "profile":
        t = f"👤 <b>پروفایل / ساعت</b>\nفونت ساعت: {FONT_NAMES[c['font']]}"
        rows = [[B(f"⏰ ساعت در نام: {onoff(c['clock'])}", "p:x:clock:c:profile", ok_style(c["clock"]))],
                [B("🔤 تغییر فونت ساعت", f"p:v:font:{(c['font'] + 1) % len(FONTS)}:c:profile", "primary")],
                [B("🔄 ریست نام", "p:x:clockreset:c:profile", "danger")]]
    elif key == "fmt":
        t = f"✍️ <b>فرمت متن</b>\nپیام‌های خروجی شما خودکار فرمت می‌شود.\nفعلی: {FMT[c['fmt']]}"
        rows = grid([B(("✅ " if k == c["fmt"] else "") + v, f"p:v:fmt:{k}:c:fmt", "success" if k == c["fmt"] else "primary")
                     for k, v in FMT.items()])
    elif key == "lists":
        t = (f"❤️ <b>دوست / دشمن / سکوت</b>\n😡 دشمن: {len(c['enemy'])} | 💚 دوست: {len(c['friend'])} | 🤐 سکوت: {len(c['mute'])}\n"
             "افزودن با ریپلای: <code>.setenemy</code> <code>.setlove</code> <code>.mute</code>\n"
             "پاسخ‌ها مؤدبانه‌اند تا اکانت بن نشود.")
        rows = [[toggle_btn("😡 پاسخ به دشمن", "enemy_on", "c:lists", c)],
                [B("➕ متن دشمن", "p:i:enemy_add:c:lists", "primary"), B("♻️ متن‌های پیش‌فرض", "p:x:enemyreset:c:lists", "primary")],
                [B("🧹 دشمن", "p:x:clearenemy:c:lists", "danger"), B("🧹 دوست", "p:x:clearfriend:c:lists", "danger"),
                 B("🧹 سکوت", "p:x:clearmute:c:lists", "danger")]]
    elif key == "secretary":
        t = (f"🤫 <b>منشی و AFK</b>\nمنشی: {h(c['secretary_text'][:120])}\nAFK: {h(c['afk_text'][:120])}")
        rows = [[toggle_btn("🤫 منشی", "secretary", "c:secretary", c), B("✏️ متن", "p:i:secretary_text:c:secretary", "primary")],
                [toggle_btn("🌙 AFK", "afk", "c:secretary", c), B("✏️ متن", "p:i:afk_text:c:secretary", "primary")]]
    elif key == "react":
        t = f"🔔 <b>ری‌اکشن خودکار</b>\nایموجی: {c['emoji']} | کاربران لیست: {len(c['react_users'])}\nلیست با <code>.react</code> (ریپلای)"
        rows = [[toggle_btn("🔔 ری‌اکشن", "react_on", "c:react", c)],
                [toggle_btn("👥 فقط لیست", "react_list", "c:react", c)]]
        rows += grid([B(("✅ " if e == c["emoji"] else "") + e, f"p:v:emoji:{e}:c:react", "success" if e == c["emoji"] else "primary")
                      for e in EMOJIS], 4)
        rows.append([B("🧹 پاکسازی لیست", "p:x:clearreact:c:react", "danger")])
    elif key == "reply":
        lst = "\n".join(f"• {h(q[:25])} ⟵ {h(a[:30])}" for q, a in list(c["replies"].items())[:8]) or "— خالی —"
        t = f"💬 <b>پاسخ خودکار</b>\n{lst}"
        rows = [[toggle_btn("💬 پاسخ خودکار", "autoreply_on", "c:reply", c)],
                [B("➕ افزودن (سوال:جواب)", "p:i:reply_add:c:reply", "primary"), B("🧹 پاکسازی", "p:x:clearreply:c:reply", "danger")]]
    elif key == "group":
        t = f"👥 <b>گروه</b>\nخوش‌آمدگویی (فقط در گروه‌هایی که ادمینید)\nمتن: {h(c['welcome_text'][:100])}"
        rows = [[toggle_btn("👋 خوش‌آمدگویی", "welcome_on", "c:group", c), B("✏️ متن", "p:i:welcome_text:c:group", "primary")],
                [toggle_btn("🔔 اعلان تگ", "tagalert", "c:group", c)]]
    elif key == "action":
        t = f"⌨️ <b>اکشن</b>\nهنگام دریافت پیام در پی‌وی، حالت انتخابی نمایش داده می‌شود."
        rows = [[toggle_btn("اکشن خودکار", "typing", "c:action", c)]]
        rows += grid([B(("✅ " if k == c["action"] else "") + v[0], f"p:v:action:{k}:c:action", "success" if k == c["action"] else "primary")
                      for k, v in ACTIONS.items()])
    elif key == "system":
        r = RUN.get(uid)
        up = int(time.time() - r.t0) if r else 0
        t = (f"📊 <b>سیستم و اطلاعات</b>\n🕒 آپ‌تایم: {up // 3600}h {up % 3600 // 60}m\n"
             f"🤖 ربات: @{BOT['username']}\n⏳ اشتراک: {fmt_remaining(meta['expire'])}")
        rows = [[B("🔄 بروزرسانی", "p:x:sys:c:system", "success")]]
    elif key == "health":
        t = "🛡 <b>سلامت اکانت</b>\nبررسی ریپورت و نشست‌های فعال اکانت"
        rows = [[B("🔍 بررسی ریپورت (SpamBot)", "p:x:health:c:health", "primary")],
                [B("🔐 نشست‌های فعال", "p:x:sessions:c:health", "primary")]]
    elif key == "tools":
        t = "🛠 <b>ابزار</b>\n" + CMD_HELP
        rows = [[B("♻️ بازنشانی تنظیمات سلف", "p:c:confirm_reset", "danger")]]
    elif key == "fun":
        t = "🎲 <b>سرگرمی</b>\nیکی را بزنید تا در Saved Messages ارسال شود (یا <code>.dice</code> در هر چت)"
        rows = [[B(e, f"p:x:{k}:c:fun", "primary") for k, e in DICE.items()]]
    else:
        return render(uid, "home", note)
    return t + nt, IK(*rows, *foot)

async def edit_inline(inline_id, text, markup):
    order = ["editMessageCaption", "editMessageText"] if CFG["panel_photo"] else ["editMessageText", "editMessageCaption"]
    for method in order:
        try:
            await bot.call(method, inline_message_id=inline_id, parse_mode="HTML", reply_markup=markup,
                           **{("caption" if method.endswith("Caption") else "text"): text})
            return True
        except TgError as e:
            if "not modified" in e.desc:
                return True
    return False

async def refresh_panel(uid, inline_id, route, note=""):
    t, kb = render(uid, route, note)
    await edit_inline(inline_id, t, kb)

async def panel_action(uid, inline_id, data):
    r = RUN.get(uid)
    if not r or str(uid) not in SELFS:
        return "❌ سلف شما فعال نیست", "home"
    c, p = SC(uid), data.split(":")[1:]
    kind = p[0] if p else "home"
    try:
        if kind == "t" and len(p) >= 3 and p[1] in TOGGLES:
            c[p[1]] = not c[p[1]]
            if p[1] == "afk":
                c["afk_since"] = now()
            selfs_store.mark()
            return None, ":".join(p[2:])
        if kind == "v" and len(p) >= 4:
            k, val, route = p[1], p[2], ":".join(p[3:])
            if k == "fmt" and val in FMT:
                c["fmt"] = val
            elif k == "online" and val in ("online", "offline", "auto"):
                c["online"] = val
            elif k == "font" and val.isdigit() and int(val) < len(FONTS):
                c["font"] = int(val)
                if c["clock"]:
                    await r.apply_clock(force=True)
            elif k == "emoji" and val in EMOJIS:
                c["emoji"] = val
            elif k == "action" and val in ACTIONS:
                c["action"] = val
            else:
                return "❌ نامعتبر", route
            selfs_store.mark()
            return None, route
        if kind == "i" and len(p) >= 3:
            label = {"secretary_text": "متن منشی", "afk_text": "متن AFK", "welcome_text": "متن خوش‌آمدگویی ({name})",
                     "enemy_add": "متن جدید پاسخ دشمن (بدون فحش)", "reply_add": "سوال:جواب"}.get(p[1])
            if not label:
                return "❌ نامعتبر", "home"
            r.pending = {"kind": p[1], "inline": inline_id, "route": ":".join(p[2:]), "t": time.time()}
            return f"✍️ {label} را همین حالا در Saved Messages بفرستید", ":".join(p[2:])
        if kind == "x" and len(p) >= 3:
            act, route = p[1], ":".join(p[2:])
            clears = {"clearenemy": "enemy", "clearfriend": "friend", "clearmute": "mute", "clearreact": "react_users"}
            if act == "clock":
                return await r.set_clock(not c["clock"]), route
            if act == "clockreset":
                return await r.set_clock(False), route
            if act in clears:
                c[clears[act]] = []
            elif act == "clearreply":
                c["replies"] = {}
            elif act == "enemyreset":
                c["enemy_texts"] = []
            elif act == "sys":
                pass
            elif act == "health":
                return await r.spambot(), route
            elif act == "sessions":
                return await r.sessions(), route
            elif act == "resetcfg":
                if c["clock"]:
                    await r.set_clock(False)
                SELFS[str(uid)]["cfg"] = {}
                SC(uid)
            elif act in DICE:
                await r.client.send_dice("me", DICE[act])
            else:
                return "❌ نامعتبر", route
            selfs_store.mark()
            return "✅ انجام شد", route
    except errors.FloodWait as e:
        return f"⏳ محدودیت تلگرام، {e.value} ثانیه صبر کنید", "home"
    except Exception as e:
        log.warning("panel_action %s: %s", uid, e)
        return "❌ خطا در اجرا", "home"
    return None, (":".join(p) if kind in ("home", "set", "acc", "onl", "c") else "home")

# ============================ Builder bot: users ================
vault = Vault()
STEP, TEMP, LOCKS = {}, {}, {}
AUTH_ERRS = tuple(getattr(errors, n) for n in (
    "AuthKeyUnregistered", "UserDeactivated", "UserDeactivatedBan", "SessionRevoked", "SessionExpired",
    "AuthKeyInvalid") if hasattr(errors, n))

M_ACT, M_ACC, M_MNG = "✅ فعالسازی سلف", "👤 حساب کاربری", "⚙️ مدیریت سلف"
M_BUY, M_HELP, M_FREE, M_ADM = "💎 خرید الماس", "🆘 راهنما و پشتیبانی", "🎁 الماس رایگان", "👑 پنل مدیریت"

def main_kb(uid):
    rows = [[B(M_ACT, style="success")],
            [B(M_ACC, style="primary"), B(M_MNG, style="primary")],
            [B(M_BUY, style="primary")],
            [B(M_HELP, style="primary"), B(M_FREE, style="primary")]]
    if is_admin(uid):
        rows.append([B(M_ADM, style="danger")])
    return RK(*rows)

def ensure_user(frm, ref=None):
    k = str(frm["id"])
    u = USERS.get(k)
    new = u is None
    if new:
        u = USERS[k] = {"id": frm["id"], "d": 0, "ref": None, "refs": 0, "ban": False, "t": now(), "daily": 0}
    u["name"], u["un"] = frm.get("first_name", ""), frm.get("username", "")
    users_store.mark()
    return u, new

def mask_phone(p):
    d = re.sub(r"\D", "", p)
    return f"+{d[:2]}{'*' * max(0, len(d) - 4)}{d[-2:]}"

async def delete_msg(m):
    try:
        await bot.call("deleteMessage", chat_id=m["chat"]["id"], message_id=m["message_id"])
    except Exception:
        pass

async def joined(uid):
    if not CFG["force_join"] or is_admin(uid):
        return True
    try:
        r = await bot.call("getChatMember", chat_id="@" + CFG["channel"], user_id=uid)
        return r["status"] in ("creator", "administrator", "member", "restricted")
    except Exception as e:
        log.warning("join check failed: %s", e)
        return True

async def send_join(uid):
    await send(uid, "📢 برای استفاده از ربات ابتدا در کانال عضو شوید، سپس «عضو شدم» را بزنید.",
               IK([B("📢 عضویت در کانال", url=f"https://t.me/{CFG['channel']}", style="primary")],
                  [B("✅ عضو شدم", "u:chk", "success")]))

async def show_menu(uid):
    await send(uid, "🌟 <b>به ربات سلف‌ساز خوش آمدید</b>\nاز دکمه‌های زیر استفاده کنید 👇",
               main_kb(uid), photo=CFG["menu_photo"])

def self_status(uid):
    s = SELFS.get(str(uid))
    if not s:
        return "غیرفعال ❌"
    if s["expire"] <= now():
        return "منقضی شده ⌛️"
    return ("فعال ✅" if uid in RUN else "خاموش ⏹") + f" ({fmt_remaining(s['expire'])})"

async def cleanup_temp(uid):
    t = TEMP.pop(uid, None)
    if t:
        try:
            await t["cl"].disconnect()
        except Exception:
            pass

# ---------- self lifecycle ----------
async def start_self(uid):
    key = str(uid)
    if uid in RUN:
        return True, ""
    try:
        blob = vault.get(uid)
    except Exception as e:
        log.error("vault read %s: %s", uid, e)
        return False, "سشن قابل خواندن نیست"
    r = SelfRunner(uid, blob["s"])
    try:
        await r.start()
    except AUTH_ERRS:
        await r.stop()
        SELFS[key]["active"] = False
        selfs_store.mark()
        return False, "سشن باطل شده؛ دوباره فعالسازی کنید"
    except Exception as e:
        await r.stop()
        log.warning("start_self %s: %s", uid, e)
        return False, "خطا در اجرای سلف"
    RUN[uid] = r
    SELFS[key]["active"] = True
    selfs_store.mark()
    return True, ""

async def stop_self(uid):
    r = RUN.pop(uid, None)
    if r:
        await r.stop()
    if str(uid) in SELFS:
        SELFS[str(uid)]["active"] = False
        selfs_store.mark()

async def drop_self(uid):
    await stop_self(uid)
    vault.delete(uid)
    SELFS.pop(str(uid), None)
    selfs_store.mark()

# ---------- menu actions ----------
async def act_account(uid):
    u = USERS[str(uid)]
    phone = SELFS.get(str(uid), {}).get("phone", "—")
    t = (f"👤 <b>حساب کاربری</b>\n\n🆔 آیدی : <code>{uid}</code>\n📱 شماره : {h(phone)}\n"
         f"💎 موجودی : <b>{u['d']}</b> الماس\n⏳ سلف : {self_status(uid)}")
    await send(uid, t, IK([B("💎 انتقال الماس", "u:tr", "primary")], [B("🔙 بازگشت", "u:back", "danger")]),
               photo=CFG["menu_photo"])

async def act_activate(uid):
    u, meta, cost = USERS[str(uid)], SELFS.get(str(uid)), CFG["cost"]
    if meta and meta["expire"] > now() and vault.exists(uid):
        if uid not in RUN:
            ok, err = await start_self(uid)
            if not ok:
                return await send(uid, "❌ " + err, main_kb(uid))
        return await send(uid, f"✅ سلف شما فعال است.\n⏳ {fmt_remaining(meta['expire'])}\nدر Saved Messages بنویسید: <b>پنل</b>", main_kb(uid))
    if u["d"] < cost:
        return await send(uid, f"❌ موجودی کافی نیست. هزینه: <b>{cost}</b> الماس | موجودی: <b>{u['d']}</b>",
                          IK([B("💎 خرید الماس", "u:buy", "primary"), B("🎁 الماس رایگان", "u:free", "success")]))
    if meta and vault.exists(uid):
        return await send(uid, f"♻️ سشن شما ذخیره است. با <b>{cost}</b> الماس سلف دوباره فعال شود؟",
                          IK([B("✅ تایید و فعالسازی", "u:s:rn", "success"), B("❌ انصراف", "u:cancel", "danger")]))
    STEP[uid] = {"n": "act_phone"}
    await send(uid, "📱 برای ورود، با دکمهٔ زیر شمارهٔ خودتان را ارسال کنید.\n"
                    "🔐 سشن با رمزنگاری AES-256 ذخیره می‌شود و رمز دومرحله‌ای ذخیره نمی‌شود.",
               {"keyboard": [[B("📲 ارسال شماره من", style="success", request_contact=True)],
                             [B("❌ انصراف", style="danger")]], "resize_keyboard": True, "one_time_keyboard": True})

async def act_manage(uid):
    meta = SELFS.get(str(uid))
    if not meta:
        return await send(uid, "سلفی ندارید. ابتدا «فعالسازی سلف» را بزنید.", main_kb(uid))
    run = uid in RUN
    await send(uid, f"⚙️ <b>مدیریت سلف</b>\n📱 {h(meta.get('phone', '—'))}\n⏳ {self_status(uid)}",
               IK([B("⏹ خاموش کردن" if run else "▶️ روشن کردن", "u:s:" + ("off" if run else "on"), "danger" if run else "success"),
                   B("🔄 ری‌استارت", "u:s:rs", "primary")],
                  [B(f"♻️ تمدید ({CFG['cost']} 💎)", "u:s:rn", "success")],
                  [B("📖 راهنما", "u:s:help", "primary"), B("🗑 حذف سلف", "u:s:del", "danger")]))

async def act_buy(uid):
    await send(uid, CFG["buy_text"], IK([B("📤 ارسال رسید پرداخت", "u:rcpt", "success")],
                                         *([[B("🛟 پشتیبانی", url=f"https://t.me/{CFG['support']}", style="primary")]] if CFG["support"] else [])),
               photo=CFG["menu_photo"])

async def act_help(uid):
    rows = [[B("🛟 پشتیبانی", url=f"https://t.me/{CFG['support']}", style="primary")]] if CFG["support"] else []
    await send(uid, CFG["help_text"], IK(*rows) if rows else None, photo=CFG["menu_photo"])

async def act_free(uid):
    u = USERS[str(uid)]
    link = f"https://t.me/{BOT['username']}?start=ref_{uid}"
    await send(uid, f"🎁 <b>الماس رایگان</b>\n\nبا هر دعوت <b>{CFG['ref_reward']}</b> الماس بگیرید.\n"
                    f"👥 دعوت‌های شما: {u['refs']}\n🔗 لینک شما:\n<code>{link}</code>",
               IK([B(f"🎁 جایزه روزانه ({CFG['daily']} 💎)", "u:daily", "success")]), photo=CFG["menu_photo"])

MENU_ACTIONS = {M_ACT: act_activate, M_ACC: act_account, M_MNG: act_manage,
                M_BUY: act_buy, M_HELP: act_help, M_FREE: act_free}

# ---------- login flow ----------
async def begin_login(uid, phone):
    await cleanup_temp(uid)
    cl = Client(f"t{uid}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
    try:
        await cl.connect()
        sent = await cl.send_code(phone)
    except errors.PhoneNumberInvalid:
        STEP.pop(uid, None)
        return await send(uid, "❌ شماره نامعتبر است", main_kb(uid))
    except errors.FloodWait as e:
        STEP.pop(uid, None)
        return await send(uid, f"⏳ محدودیت تلگرام؛ {e.value} ثانیه بعد تلاش کنید", main_kb(uid))
    except Exception as e:
        log.warning("send_code: %s", e)
        STEP.pop(uid, None)
        try:
            await cl.disconnect()
        except Exception:
            pass
        return await send(uid, "❌ اتصال ناموفق بود؛ دوباره تلاش کنید", main_kb(uid))
    TEMP[uid] = {"cl": cl, "phone": phone, "hash": sent.phone_code_hash, "t": now()}
    STEP[uid] = {"n": "act_code"}
    await send(uid, "✅ کد ارسال شد. کد ۵ رقمی را <b>با نقطه</b> بفرستید:\n<code>1.2.3.4.5</code>\n"
                    "(ارسال بدون نقطه باعث باطل شدن کد توسط تلگرام می‌شود)", main_kb(uid))

async def finish_login(uid):
    t = TEMP.pop(uid, None)
    STEP.pop(uid, None)
    if not t:
        return
    cl, u = t["cl"], USERS[str(uid)]
    try:
        ss = await cl.export_session_string()
        await cl.disconnect()
    except Exception as e:
        log.warning("export session: %s", e)
        return await send(uid, "❌ خطا در ذخیره سشن", main_kb(uid))
    if u["d"] < CFG["cost"]:
        return await send(uid, "❌ موجودی کافی نیست", main_kb(uid))
    vault.put(uid, {"s": ss, "p": t["phone"]})
    u["d"] -= CFG["cost"]
    SELFS[str(uid)] = {"expire": now() + CFG["days"] * 86400, "active": False, "phone": mask_phone(t["phone"]),
                       "name": "", "cfg": {}, "warned": False}
    selfs_store.mark()
    users_store.mark()
    ok, err = await start_self(uid)
    if ok:
        await send(uid, f"🎉 سلف فعال شد! مدت: {CFG['days']} روز\n\nدر <b>Saved Messages</b> کلمهٔ <b>پنل</b> را بفرستید.", main_kb(uid))
    else:
        u["d"] += CFG["cost"]
        await drop_self(uid)
        await send(uid, f"❌ {err}. الماس برگشت داده شد.", main_kb(uid))

async def on_step(uid, m, text, st):
    n = st["n"]
    if text in ("❌ انصراف", "/cancel"):
        STEP.pop(uid, None)
        await cleanup_temp(uid)
        return await send(uid, "لغو شد.", main_kb(uid))
    if n == "act_phone":
        c = m.get("contact")
        if not c or c.get("user_id") != uid:
            return await send(uid, "⚠️ فقط با دکمهٔ «ارسال شماره من» شمارهٔ خودتان را بفرستید")
        return await begin_login(uid, "+" + re.sub(r"\D", "", c["phone_number"]))
    if n in ("act_code", "act_pass"):
        t = TEMP.get(uid)
        await delete_msg(m)
        if not t:
            STEP.pop(uid, None)
            return await send(uid, "⏳ نشست ورود منقضی شد؛ دوباره فعالسازی بزنید", main_kb(uid))
        try:
            if n == "act_code":
                digits = re.sub(r"\D", "", text)
                if len(digits) != 5:
                    return await send(uid, "⚠️ فرمت درست: <code>1.2.3.4.5</code>")
                await t["cl"].sign_in(t["phone"], t["hash"], digits)
            else:
                await t["cl"].check_password(text)
        except errors.SessionPasswordNeeded:
            STEP[uid] = {"n": "act_pass"}
            return await send(uid, "🔑 رمز تأیید دومرحله‌ای را بفرستید (پیام شما بلافاصله حذف می‌شود):")
        except errors.PhoneCodeInvalid:
            return await send(uid, "❌ کد اشتباه است، دوباره بفرستید")
        except errors.PasswordHashInvalid:
            return await send(uid, "❌ رمز اشتباه است، دوباره بفرستید")
        except (errors.PhoneCodeExpired, errors.BadRequest) as e:
            await cleanup_temp(uid)
            STEP.pop(uid, None)
            return await send(uid, f"⌛️ کد منقضی شد ({type(e).__name__}). دوباره فعالسازی بزنید", main_kb(uid))
        except errors.FloodWait as e:
            return await send(uid, f"⏳ {e.value} ثانیه صبر کنید")
        return await finish_login(uid)
    if n == "tr_id":
        if not text.isdigit() or text not in USERS or int(text) == uid:
            return await send(uid, "❌ کاربر پیدا نشد (باید قبلاً ربات را استارت کرده باشد)")
        STEP[uid] = {"n": "tr_amt", "to": text}
        return await send(uid, f"💎 تعداد الماس (موجودی: {USERS[str(uid)]['d']}):")
    if n == "tr_amt":
        u, to = USERS[str(uid)], st["to"]
        if not text.isdigit() or not (0 < int(text) <= u["d"]):
            return await send(uid, "❌ مقدار نامعتبر یا بیشتر از موجودی")
        a = int(text)
        u["d"] -= a
        USERS[to]["d"] += a
        users_store.mark()
        STEP.pop(uid, None)
        await send(uid, f"✅ {a} الماس منتقل شد.", main_kb(uid))
        return await safe_send(int(to), f"💎 {a} الماس از طرف <code>{uid}</code> دریافت کردید.")
    if n == "receipt":
        STEP.pop(uid, None)
        for o in {*ENV_OWNERS, *CFG["owners"]}:
            try:
                await bot.call("copyMessage", chat_id=o, from_chat_id=uid, message_id=m["message_id"])
                await send(o, f"🧾 رسید از <a href='tg://user?id={uid}'>{h(USERS[str(uid)].get('name', ''))}</a> (<code>{uid}</code>)",
                           IK([B("✅ تایید و شارژ", f"a:rc:{uid}", "success"), B("❌ رد", f"a:rr:{uid}", "danger")]))
            except Exception as e:
                log.info("receipt fwd: %s", e)
        return await send(uid, "✅ رسید ارسال شد؛ پس از بررسی الماس شارژ می‌شود.", main_kb(uid))
    if is_admin(uid):
        return await admin_step(uid, m, text, st)
    STEP.pop(uid, None)

async def user_cb(cb, uid, parts):
    """callbackهای پیام‌های ربات (u:...)"""
    act, u = parts[1], USERS[str(uid)]
    msg = cb["message"]
    chat = msg["chat"]["id"]
    if act == "back" or act == "cancel":
        STEP.pop(uid, None)
        await delete_msg(msg)
        return await show_menu(uid)
    if act == "chk":
        if await joined(uid):
            await delete_msg(msg)
            return await show_menu(uid)
        return await bot.call("answerCallbackQuery", callback_query_id=cb["id"], text="❌ هنوز عضو نیستید", show_alert=True)
    if act == "tr":
        STEP[uid] = {"n": "tr_id"}
        return await send(chat, "🆔 آیدی عددی گیرنده را بفرستید:")
    if act == "buy":
        return await act_buy(uid)
    if act == "free":
        return await act_free(uid)
    if act == "rcpt":
        STEP[uid] = {"n": "receipt"}
        return await send(chat, "📤 تصویر یا متن رسید را بفرستید:")
    if act == "daily":
        if now() - u["daily"] < 86400:
            return await bot.call("answerCallbackQuery", callback_query_id=cb["id"],
                                  text=f"⏳ {fmt_remaining(u['daily'] + 86400)} دیگر", show_alert=True)
        u["daily"], u["d"] = now(), u["d"] + CFG["daily"]
        users_store.mark()
        return await bot.call("answerCallbackQuery", callback_query_id=cb["id"], text=f"🎁 {CFG['daily']} الماس اضافه شد", show_alert=True)
    if act == "s" and len(parts) > 2:
        sub, meta = parts[2], SELFS.get(str(uid))
        if sub == "help":
            return await send(chat, CFG["help_text"])
        if not meta:
            return await send(chat, "سلفی ندارید.")
        if sub == "off":
            await stop_self(uid)
        elif sub in ("on", "rs"):
            if meta["expire"] <= now():
                return await send(chat, "⌛️ اشتراک منقضی شده؛ تمدید کنید.")
            await stop_self(uid)
            ok, err = await start_self(uid)
            if not ok:
                return await send(chat, "❌ " + err)
        elif sub == "rn":
            if u["d"] < CFG["cost"]:
                return await send(chat, "❌ موجودی کافی نیست")
            u["d"] -= CFG["cost"]
            meta["expire"] = max(meta["expire"], now()) + CFG["days"] * 86400
            meta["warned"] = False
            users_store.mark()
            selfs_store.mark()
            if uid not in RUN:
                ok, err = await start_self(uid)
                if not ok:
                    u["d"] += CFG["cost"]
                    return await send(chat, "❌ " + err)
            await send(chat, f"✅ تمدید شد: {fmt_remaining(meta['expire'])}")
        elif sub == "del":
            return await send(chat, "⚠️ حذف قطعی سلف و سشن؟ (الماس برنمی‌گردد)",
                              IK([B("🗑 بله، حذف شود", "u:s:del2", "danger"), B("❌ لغو", "u:cancel", "primary")]))
        elif sub == "del2":
            await drop_self(uid)
            return await send(chat, "🗑 سلف و سشن حذف شد.", main_kb(uid))
        await delete_msg(msg)
        return await act_manage(uid)

# ============================ Admin panel =======================
async def edit(cb, text, kb=None):
    msg = cb["message"]
    kw = dict(chat_id=msg["chat"]["id"], message_id=msg["message_id"], parse_mode="HTML", reply_markup=kb)
    try:
        await bot.call("editMessageText", text=text, link_preview_options={"is_disabled": True}, **kw)
    except TgError as e:
        if "not modified" in e.desc:
            return
        try:
            await bot.call("editMessageCaption", caption=text, **kw)
        except TgError:
            await send(msg["chat"]["id"], text, kb)

BACK = [B("🔙 پنل مدیریت", "a:home", "danger")]

def adm_home():
    return "👑 <b>پنل مدیریت پیشرفته</b>", IK(
        [B("📊 آمار", "a:stats", "primary"), B("📢 ارسال همگانی", "a:bc", "primary")],
        [B("🖼 عکس منو", "a:ph:menu", "success"), B("🖼 عکس پنل سلف", "a:ph:panel", "success")],
        [B("🎛 مدیریت دکمه‌های پنل", "a:pb", "primary")],
        [B("💎 الماس", "a:dm", "primary"), B("🚫 بن / آنبن", "a:ban", "primary")],
        [B("🧩 مدیریت سلف‌ها", "a:sl:0", "primary")],
        [B("⚙️ تنظیمات", "a:st", "primary"), B("👥 ادمین‌ها", "a:ad", "primary")],
        [B("🔐 امنیت", "a:sec", "primary")],
        [B("❌ بستن", "a:close", "danger")])

async def admin_home(uid):
    t, kb = adm_home()
    await send(uid, t, kb)

def adm_pb():
    rows = [[B(("✅ " if CFG["panel"][k]["on"] else "🚫 ") + CFG["panel"][k]["t"], f"a:pbk:{k}", CFG["panel"][k]["s"])]
            for k in CFG["panel_order"] if k in CFG["panel"]]
    return "🎛 <b>مدیریت دکمه‌های پنل سلف</b>\nروی هر دکمه بزنید تا رنگ/نام/ترتیب/نمایش را کنترل کنید.", IK(
        *rows, [B("🔗 دکمه‌های لینکی", "a:pl", "primary")], BACK)

def adm_pbk(k):
    p = CFG["panel"][k]
    return (f"🎛 <b>{h(p['t'])}</b>\nوضعیت: {onoff(p['on'])}\nرنگ: {STYLE_NAME[p['s']]}"), IK(
        [B(f"نمایش: {onoff(p['on'])}", f"a:pbt:{k}", ok_style(p["on"])), B("🎨 تغییر رنگ", f"a:pbc:{k}", p["s"])],
        [B("✏️ تغییر نام", f"a:pbn:{k}", "primary"), B("⬆️", f"a:pbu:{k}", "primary"), B("⬇️", f"a:pbd:{k}", "primary")],
        [B("🔙 لیست دکمه‌ها", "a:pb", "danger")])

def adm_links():
    rows = [[B(f"🗑 {l['text']}", f"a:pld:{i}", "danger")] for i, l in enumerate(CFG["links"])]
    return "🔗 <b>دکمه‌های لینکی زیر پنل</b>\n" + ("" if rows else "— خالی —"), IK(
        *rows, [B("➕ افزودن لینک", "a:pla", "success")], [B("🔙 لیست دکمه‌ها", "a:pb", "danger")])

SET_LABELS = {"cost": "💎 هزینه فعالسازی", "days": "📅 روز اشتراک", "ref_reward": "🎁 پاداش دعوت", "daily": "🎁 جایزه روزانه",
              "channel": "🔗 کانال جوین", "support": "🛟 یوزرنیم پشتیبان", "buy_text": "🛒 متن خرید",
              "help_text": "📖 متن راهنما", "bad_words": "🚫 کلمات ممنوعه", "enemy_texts": "😡 متن‌های پیش‌فرض دشمن"}

def adm_settings():
    rows = [[B(f"{SET_LABELS[k]}: {CFG[k]}", f"a:sv:{k}", "primary")] for k in ("cost", "days", "ref_reward", "daily")]
    rows += [[B(f"📢 جوین اجباری: {onoff(CFG['force_join'])}", "a:tg:force_join", ok_style(CFG["force_join"])),
              B(f"🔗 @{CFG['channel']}", "a:sv:channel", "primary")],
             [B(f"🔧 ربات: {onoff(CFG['bot_on'])}", "a:tg:bot_on", ok_style(CFG["bot_on"]))],
             [B("🛟 پشتیبان", "a:sv:support", "primary"), B("🛒 متن خرید", "a:sv:buy_text", "primary")],
             [B("📖 متن راهنما", "a:sv:help_text", "primary")],
             [B("🚫 کلمات ممنوعه", "a:sv:bad_words", "primary"), B("😡 متن دشمن", "a:sv:enemy_texts", "primary")]]
    return "⚙️ <b>تنظیمات ربات</b>", IK(*rows, BACK)

def apply_setting(key, text):
    if key in ("cost", "days", "ref_reward", "daily"):
        if not text.isdigit() or not (0 <= int(text) <= 100000):
            return False, "❌ عدد معتبر بفرستید"
        CFG[key] = int(text)
    elif key == "channel":
        CFG[key] = text.lstrip("@").strip()
    elif key == "support":
        CFG[key] = text.lstrip("@").strip()
    elif key in ("buy_text", "help_text"):
        CFG[key] = text
    elif key == "bad_words":
        CFG["bad_words"] = [w.strip() for w in re.split(r"[,\n،]", text) if w.strip()]
    elif key == "enemy_texts":
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if any(has_bad_word(l) for l in lines):
            return False, "⛔ متن‌ها شامل الفاظ نامناسب است؛ برای امنیت اکانت‌ها مجاز نیست"
        CFG["enemy_texts"] = lines
    cfg_store.mark()
    return True, "✅ ذخیره شد"

async def broadcast(admin, mid):
    ok = fail = 0
    for k in list(USERS):
        try:
            await bot.call("copyMessage", chat_id=int(k), from_chat_id=admin, message_id=mid)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await safe_send(admin, f"📢 ارسال همگانی تمام شد\n✅ موفق: {ok}\n❌ ناموفق: {fail}")

def sl_page(page):
    items = sorted(SELFS.items(), key=lambda x: x[1]["expire"])
    chunk = items[page * 8:(page + 1) * 8]
    rows = [[B(f"{'🟢' if int(k) in RUN else '⚪️'} {k} | {max(0, (v['expire'] - now()) // 86400)}d", f"a:sd:{k}", "primary")]
            for k, v in chunk]
    nav = []
    if page > 0:
        nav.append(B("⬅️", f"a:sl:{page - 1}", "primary"))
    if (page + 1) * 8 < len(items):
        nav.append(B("➡️", f"a:sl:{page + 1}", "primary"))
    return f"🧩 <b>سلف‌ها</b> ({len(items)})", IK(*rows, nav, BACK)

def sd_page(k):
    v = SELFS[k]
    run = int(k) in RUN
    return (f"🧩 <b>سلف {k}</b>\n👤 {h(v.get('name', ''))}\n📱 {h(v.get('phone', ''))}\n⏳ {fmt_remaining(v['expire'])}\n"
            f"وضعیت: {'🟢 در حال اجرا' if run else '⚪️ متوقف'}"), IK(
        [B("➕ افزودن روز", f"a:sda:{k}", "success"), B("⏹ توقف" if run else "▶️ شروع", f"a:sdt:{k}", "danger" if run else "success")],
        [B("🗑 حذف کامل", f"a:sdx:{k}", "danger")], [B("🔙 لیست", "a:sl:0", "primary")])

def ad_page():
    admins = ", ".join(f"<code>{a}</code>" for a in CFG["admins"]) or "—"
    owners = ", ".join(f"<code>{o}</code>" for o in sorted(ENV_OWNERS | set(CFG["owners"])))
    return f"👥 <b>ادمین‌ها:</b> {admins}\n👑 <b>مالک‌ها:</b> {owners}", IK(
        [B("➕ ادمین", "a:ada", "success"), B("➖ ادمین", "a:add", "danger")],
        [B("➕ مالک", "a:owa", "success"), B("➖ مالک", "a:owd", "danger")], BACK)

async def admin_cb(cb, uid, parts):
    act = parts[1]
    owner_only = {"owa", "owd", "ada", "add", "sec"}
    if act in owner_only and not is_owner(uid):
        return await bot.call("answerCallbackQuery", callback_query_id=cb["id"], text="⛔ فقط مالک", show_alert=True)
    arg = parts[2] if len(parts) > 2 else ""
    if act == "home":
        STEP.pop(uid, None)
        return await edit(cb, *adm_home())
    if act == "close":
        return await delete_msg(cb["message"])
    if act == "stats":
        act_n = sum(1 for s in SELFS.values() if s.get("active") and s["expire"] > now())
        t = (f"📊 <b>آمار</b>\n👥 کاربران: {len(USERS)}\n🚫 بن‌شده: {sum(1 for u in USERS.values() if u['ban'])}\n"
             f"🧩 سلف ثبت‌شده: {len(SELFS)}\n🟢 در حال اجرا: {len(RUN)}\n✅ اشتراک فعال: {act_n}\n"
             f"💎 مجموع الماس کاربران: {sum(u['d'] for u in USERS.values())}")
        return await edit(cb, t, IK(BACK))
    if act == "bc":
        STEP[uid] = {"n": "bc"}
        return await edit(cb, "📢 پیام همگانی را بفرستید (متن/عکس/…)", IK(BACK))
    if act == "bcy":
        st = STEP.pop(uid, None)
        if st and st.get("n") == "bc_ok":
            asyncio.create_task(broadcast(uid, st["mid"]))
            return await edit(cb, "⏳ ارسال شروع شد؛ گزارش پایانی می‌آید.", IK(BACK))
    if act == "bcn":
        STEP.pop(uid, None)
        return await edit(cb, *adm_home())
    if act in ("ph", "phs", "phd"):
        k = arg
        if act == "phd":
            CFG[k + "_photo"] = ""
            cfg_store.mark()
        if act == "phs":
            STEP[uid] = {"n": "photo", "k": k}
            return await edit(cb, "🖼 عکس را به‌صورت <b>Photo</b> (نه فایل) بفرستید:", IK(BACK))
        name = "منوی ربات" if k == "menu" else "پنل سلف (Saved Messages)"
        return await edit(cb, f"🖼 <b>عکس {name}</b>\nوضعیت: {'✅ تنظیم شده' if CFG[k + '_photo'] else '❌ ندارد'}", IK(
            [B("📤 ارسال عکس جدید", f"a:phs:{k}", "success"), B("🗑 حذف", f"a:phd:{k}", "danger")], BACK))
    if act == "pb":
        return await edit(cb, *adm_pb())
    if act.startswith("pb") and act != "pb" and arg in CFG["panel"]:
        p = CFG["panel"][arg]
        if act == "pbt":
            p["on"] = not p["on"]
        elif act == "pbc":
            p["s"] = STYLES[(STYLES.index(p["s"]) + 1) % len(STYLES)]
        elif act == "pbn":
            STEP[uid] = {"n": "pb_name", "k": arg}
            return await edit(cb, f"✏️ نام جدید دکمه «{h(p['t'])}» را بفرستید (می‌توانید ایموجی بگذارید):", IK(BACK))
        elif act in ("pbu", "pbd"):
            o, i = CFG["panel_order"], CFG["panel_order"].index(arg)
            j = i - 1 if act == "pbu" else i + 1
            if 0 <= j < len(o):
                o[i], o[j] = o[j], o[i]
        cfg_store.mark()
        return await edit(cb, *adm_pbk(arg))
    if act == "pbk" and arg in CFG["panel"]:
        return await edit(cb, *adm_pbk(arg))
    if act == "pl":
        return await edit(cb, *adm_links())
    if act == "pla":
        STEP[uid] = {"n": "link_add"}
        return await edit(cb, "🔗 به این شکل بفرستید:\n<code>متن دکمه | https://example.com</code>", IK(BACK))
    if act == "pld" and arg.isdigit() and int(arg) < len(CFG["links"]):
        CFG["links"].pop(int(arg))
        cfg_store.mark()
        return await edit(cb, *adm_links())
    if act == "dm":
        STEP[uid] = {"n": "dm_id"}
        return await edit(cb, "💎 آیدی عددی کاربر را بفرستید:", IK(BACK))
    if act == "ban":
        STEP[uid] = {"n": "ban_id"}
        return await edit(cb, "🚫 آیدی عددی کاربر را بفرستید (بن/آنبن):", IK(BACK))
    if act == "sl":
        return await edit(cb, *sl_page(int(arg or 0)))
    if act == "sd" and arg in SELFS:
        return await edit(cb, *sd_page(arg))
    if act in ("sda", "sdt", "sdx", "sdx2") and arg in SELFS:
        i = int(arg)
        if act == "sda":
            STEP[uid] = {"n": "sd_days", "k": arg}
            return await edit(cb, "➕ تعداد روز (می‌تواند منفی باشد):", IK(BACK))
        if act == "sdt":
            if i in RUN:
                await stop_self(i)
            else:
                await start_self(i)
        if act == "sdx":
            return await edit(cb, f"⚠️ حذف کامل سلف {arg}؟", IK([B("🗑 بله", f"a:sdx2:{arg}", "danger"), B("❌ خیر", f"a:sd:{arg}", "primary")]))
        if act == "sdx2":
            await drop_self(i)
            return await edit(cb, "🗑 حذف شد", IK([B("🔙 لیست", "a:sl:0", "primary")]))
        return await edit(cb, *sd_page(arg))
    if act == "st":
        return await edit(cb, *adm_settings())
    if act == "tg" and arg in ("force_join", "bot_on"):
        CFG[arg] = not CFG[arg]
        cfg_store.mark()
        return await edit(cb, *adm_settings())
    if act == "sv" and arg in SET_LABELS:
        STEP[uid] = {"n": "set", "k": arg}
        hint = "\n(هر متن در یک خط)" if arg == "enemy_texts" else ("\n(با ویرگول جدا کنید)" if arg == "bad_words" else "")
        return await edit(cb, f"{SET_LABELS[arg]} — مقدار جدید را بفرستید:{hint}", IK([B("🔙 تنظیمات", "a:st", "danger")]))
    if act == "ad":
        return await edit(cb, *ad_page())
    if act in ("ada", "add", "owa", "owd"):
        STEP[uid] = {"n": "role", "a": act}
        return await edit(cb, "🆔 آیدی عددی را بفرستید:", IK(BACK))
    if act == "sec":
        t = (f"🔐 <b>امنیت</b>\nرمزنگاری سشن: AES-256-GCM + scrypt\nسشن‌های رمزشده: {vault.count()}\n"
             f"منبع کلید: {'ENC_KEY (متغیر محیطی ✅)' if vault.from_env else '⚠️ فایل روی دیسک — ENC_KEY را در Railway تنظیم کنید'}\n"
             f"سلف‌های در حال اجرا: {len(RUN)}\nرمز دومرحله‌ای کاربران ذخیره نمی‌شود.")
        return await edit(cb, t, IK(BACK))
    if act in ("rc", "rr") and arg.isdigit() and arg in USERS:
        if act == "rr":
            await safe_send(int(arg), "❌ رسید شما رد شد. با پشتیبانی تماس بگیرید.")
            return await edit(cb, f"❌ رسید {arg} رد شد.")
        STEP[uid] = {"n": "rc_amt", "to": arg}
        return await edit(cb, f"💎 تعداد الماس برای شارژ کاربر <code>{arg}</code>:")

async def admin_step(uid, m, text, st):
    n = st["n"]
    if n == "bc":
        STEP[uid] = {"n": "bc_ok", "mid": m["message_id"]}
        return await send(uid, "ارسال برای همهٔ کاربران؟", IK([B("✅ ارسال", "a:bcy", "success"), B("❌ لغو", "a:bcn", "danger")]))
    if n == "photo":
        if not m.get("photo"):
            return await send(uid, "⚠️ باید Photo باشد؛ دوباره بفرستید")
        CFG[st["k"] + "_photo"] = m["photo"][-1]["file_id"]
        cfg_store.mark()
        STEP.pop(uid, None)
        return await send(uid, "✅ عکس ذخیره شد", IK(BACK), photo=CFG[st["k"] + "_photo"])
    if n == "pb_name":
        if not text or len(text) > 40:
            return await send(uid, "❌ نام نامعتبر")
        CFG["panel"][st["k"]]["t"] = text
        cfg_store.mark()
        STEP.pop(uid, None)
        return await send(uid, *adm_pbk(st["k"]))
    if n == "link_add":
        m2 = re.match(r"^(.{1,40}?)\s*\|\s*((?:https?|tg)://\S+)$", text)
        if not m2:
            return await send(uid, "❌ فرمت: <code>متن | https://...</code>")
        CFG["links"].append({"text": m2.group(1), "url": m2.group(2), "s": "primary"})
        cfg_store.mark()
        STEP.pop(uid, None)
        return await send(uid, *adm_links())
    if n in ("dm_id", "ban_id", "role") and not text.lstrip("-").isdigit():
        return await send(uid, "❌ آیدی عددی بفرستید")
    if n == "dm_id":
        if text not in USERS:
            return await send(uid, "❌ کاربر پیدا نشد")
        STEP[uid] = {"n": "dm_amt", "to": text}
        return await send(uid, f"💎 موجودی فعلی: {USERS[text]['d']}\nمقدار را با + یا - بفرستید (مثلاً +50 یا -10):")
    if n == "dm_amt":
        if not re.fullmatch(r"[+-]?\d{1,7}", text):
            return await send(uid, "❌ مثل +50 یا -10")
        u = USERS[st["to"]]
        u["d"] = max(0, u["d"] + int(text))
        users_store.mark()
        STEP.pop(uid, None)
        await safe_send(int(st["to"]), f"💎 موجودی شما توسط مدیریت تغییر کرد: <b>{u['d']}</b>")
        return await send(uid, f"✅ موجودی جدید: {u['d']}", IK(BACK))
    if n == "rc_amt":
        if not text.isdigit() or int(text) <= 0:
            return await send(uid, "❌ عدد مثبت بفرستید")
        USERS[st["to"]]["d"] += int(text)
        users_store.mark()
        STEP.pop(uid, None)
        await safe_send(int(st["to"]), f"✅ پرداخت تایید شد؛ <b>{text}</b> الماس شارژ شد.")
        return await send(uid, "✅ شارژ شد", IK(BACK))
    if n == "ban_id":
        if text not in USERS or is_admin(int(text)):
            return await send(uid, "❌ کاربر پیدا نشد یا ادمین است")
        u = USERS[text]
        u["ban"] = not u["ban"]
        users_store.mark()
        STEP.pop(uid, None)
        if u["ban"] and int(text) in RUN:
            await stop_self(int(text))
        return await send(uid, f"{'🚫 بن شد' if u['ban'] else '✅ آنبن شد'}: {text}", IK(BACK))
    if n == "sd_days":
        if not re.fullmatch(r"-?\d{1,4}", text):
            return await send(uid, "❌ عدد بفرستید")
        SELFS[st["k"]]["expire"] += int(text) * 86400
        SELFS[st["k"]]["warned"] = False
        selfs_store.mark()
        STEP.pop(uid, None)
        return await send(uid, *sd_page(st["k"]))
    if n == "set":
        ok, msg = apply_setting(st["k"], text)
        if ok:
            STEP.pop(uid, None)
        await send(uid, msg)
        if ok:
            await send(uid, *adm_settings())
        return
    if n == "role":
        a, t = st["a"], int(text)
        if a in ("owa", "owd") and not is_owner(uid):
            return
        lst = CFG["admins"] if a in ("ada", "add") else CFG["owners"]
        if a in ("ada", "owa") and t not in lst:
            lst.append(t)
        if a in ("add", "owd"):
            if t in ENV_OWNERS:
                return await send(uid, "⛔ مالک اصلی (ENV) قابل حذف نیست")
            if t in lst:
                lst.remove(t)
        cfg_store.mark()
        STEP.pop(uid, None)
        return await send(uid, *ad_page())

# ============================ Dispatch ==========================
async def on_msg(m):
    if m["chat"]["type"] != "private":
        return
    frm = m["from"]
    uid = frm["id"]
    if frm.get("is_bot"):
        return
    text = (m.get("text") or "").strip()
    ref = None
    if text.startswith("/start"):
        p = text.split()
        if len(p) > 1 and p[1].startswith("ref_") and p[1][4:].isdigit():
            ref = int(p[1][4:])
    u, new = ensure_user(frm)
    if new and ref and ref != uid and str(ref) in USERS:
        u["ref"] = ref
        USERS[str(ref)]["d"] += CFG["ref_reward"]
        USERS[str(ref)]["refs"] += 1
        users_store.mark()
        await safe_send(ref, f"🎁 یک نفر با لینک شما وارد شد؛ <b>{CFG['ref_reward']}</b> الماس گرفتید.")
    if u["ban"] and not is_admin(uid):
        return
    if not CFG["bot_on"] and not is_admin(uid):
        return await safe_send(uid, "🛠 ربات موقتاً در دست تعمیر است")
    if not await joined(uid):
        STEP.pop(uid, None)
        return await send_join(uid)
    if text.startswith("/start") or text == "/menu":
        STEP.pop(uid, None)
        await cleanup_temp(uid)
        return await show_menu(uid)
    if (text == "/panel" or text == M_ADM) and is_admin(uid):
        STEP.pop(uid, None)
        return await admin_home(uid)
    if text in MENU_ACTIONS:
        STEP.pop(uid, None)
        await cleanup_temp(uid)
        return await MENU_ACTIONS[text](uid)
    st = STEP.get(uid)
    if st:
        return await on_step(uid, m, text, st)
    await show_menu(uid)

async def cb_panel(cb):
    uid, data, iid = cb["from"]["id"], cb["data"], cb["inline_message_id"]
    if data == "p:close":
        r = RUN.get(uid)
        await bot.call("answerCallbackQuery", callback_query_id=cb["id"])
        try:
            if r:
                return await r.delete_panels()
        except Exception as e:
            log.info("close panel: %s", e)
        return await edit_inline(iid, "✖️ پنل بسته شد", {"inline_keyboard": []})
    toast, route = await panel_action(uid, iid, data)
    await bot.call("answerCallbackQuery", callback_query_id=cb["id"], text=(toast or "")[:190] or None,
                   show_alert=data.startswith("p:i:"))
    if str(uid) in SELFS:
        await refresh_panel(uid, iid, route, note=toast or "")

async def on_cb(cb):
    uid, data = cb["from"]["id"], cb.get("data", "")
    if cb.get("inline_message_id") and data.startswith("p:"):
        return await cb_panel(cb)
    if not cb.get("message"):
        return await bot.call("answerCallbackQuery", callback_query_id=cb["id"])
    ensure_user(cb["from"])
    parts = data.split(":")
    if USERS[str(uid)]["ban"] and not is_admin(uid):
        return await bot.call("answerCallbackQuery", callback_query_id=cb["id"])
    if parts[0] == "a" and not is_admin(uid):
        return await bot.call("answerCallbackQuery", callback_query_id=cb["id"], text="⛔", show_alert=True)
    if parts[0] not in ("a", "u") or len(parts) < 2:
        return await bot.call("answerCallbackQuery", callback_query_id=cb["id"])
    # daily / chk خودشان با پیام هشدار پاسخ می‌دهند
    if not (parts[0] == "u" and parts[1] in ("daily", "chk")):
        await bot.call("answerCallbackQuery", callback_query_id=cb["id"])
    if parts[0] == "a":
        return await admin_cb(cb, uid, parts)
    return await user_cb(cb, uid, parts)

async def on_inline(q):
    uid = q["from"]["id"]
    if q.get("query", "").strip() != "panel":
        return await bot.call("answerInlineQuery", inline_query_id=q["id"], results=[], cache_time=0)
    if uid in RUN:
        t, kb = render(uid, "home")
        if CFG["panel_photo"]:
            res = {"type": "photo", "id": "panel", "photo_file_id": CFG["panel_photo"], "caption": t,
                   "parse_mode": "HTML", "reply_markup": kb}
        else:
            res = {"type": "article", "id": "panel", "title": "پنل سلف", "description": "باز کردن پنل",
                   "input_message_content": {"message_text": t, "parse_mode": "HTML"}, "reply_markup": kb}
    else:
        res = {"type": "article", "id": "off", "title": "سلف فعال نیست",
               "input_message_content": {"message_text": "❌ سلف شما فعال نیست. از ربات سازنده فعالسازی کنید."}}
    await bot.call("answerInlineQuery", inline_query_id=q["id"], results=[res], cache_time=0, is_personal=True)

async def dispatch(u):
    obj = u.get("message") or u.get("callback_query") or u.get("inline_query") or {}
    key = obj.get("from", {}).get("id")
    async with LOCKS.setdefault(key, asyncio.Lock()):
        try:
            if "message" in u:
                await on_msg(u["message"])
            elif "callback_query" in u:
                await on_cb(u["callback_query"])
            elif "inline_query" in u:
                await on_inline(u["inline_query"])
        except Exception:
            log.exception("update failed")

async def poll():
    offset = 0
    while True:
        try:
            ups = await bot.call("getUpdates", offset=offset, timeout=50,
                                 allowed_updates=["message", "callback_query", "inline_query"])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("getUpdates: %s", e)
            await asyncio.sleep(3)
            continue
        for u in ups:
            offset = u["update_id"] + 1
            asyncio.create_task(dispatch(u))

# ============================ Background ========================
async def expiry_loop():
    while True:
        await asyncio.sleep(300)
        t = now()
        for k, v in list(SELFS.items()):
            uid = int(k)
            if v.get("active") and v["expire"] <= t:
                await stop_self(uid)
                await safe_send(uid, "⌛️ اشتراک سلف شما تمام شد. از «مدیریت سلف» تمدید کنید.")
            elif v.get("active") and v["expire"] - t < 3 * 86400 and not v.get("warned"):
                v["warned"] = True
                selfs_store.mark()
                await safe_send(uid, f"⏰ اشتراک سلف شما {fmt_remaining(v['expire'])} دیگر تمام می‌شود.")
        for uid, tmp in list(TEMP.items()):
            if t - tmp["t"] > 600:
                STEP.pop(uid, None)
                await cleanup_temp(uid)

async def resume_selfs():
    for k, v in list(SELFS.items()):
        if v.get("active") and v["expire"] > now():
            ok, err = await start_self(int(k))
            if not ok:
                await safe_send(int(k), f"⚠️ {err}")
            await asyncio.sleep(1.5)

async def shutdown():
    for uid in list(RUN):
        await RUN.pop(uid).stop()
    for s in JStore._all:
        s.flush()
    if bot.sess:
        await bot.sess.close()

async def main():
    import signal
    me = await bot.call("getMe")
    BOT.update(id=me["id"], username=me["username"])
    if not me.get("supports_inline_queries"):
        log.warning("⚠️ Inline Mode خاموش است! در BotFather: /setinline را بزنید وگرنه پنل Saved Messages کار نمی‌کند.")
    await bot.call("deleteWebhook")
    asyncio.create_task(flusher())
    asyncio.create_task(expiry_loop())
    asyncio.create_task(resume_selfs())
    task = asyncio.create_task(poll())
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, task.cancel)
        except NotImplementedError:
            pass
    log.info("✅ @%s آماده است", BOT["username"])
    try:
        await task
    except asyncio.CancelledError:
        pass
    finally:
        await shutdown()

if __name__ == "__main__":
    asyncio.run(main())