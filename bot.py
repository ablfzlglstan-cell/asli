import asyncio, logging, os, sqlite3
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

TOKEN=os.getenv("BOT_TOKEN","").strip()
OWNER_ID=int(os.getenv("OWNER_ID","0"))
DB=os.getenv("DB_PATH","fox_reporter_pro.db")
dp=Dispatcher(); waiting={}
logging.basicConfig(level=logging.INFO)

def connect(): return sqlite3.connect(DB)
def now(): return datetime.now(timezone.utc).isoformat()
def init():
    with connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS admins(uid INTEGER PRIMARY KEY, role TEXT, active INTEGER, added TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, username TEXT, body TEXT, status TEXT DEFAULT 'open', reply TEXT, created TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, actor INTEGER, event TEXT, created TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS demos(id INTEGER PRIMARY KEY AUTOINCREMENT, actor INTEGER, created TEXT)")
        c.execute("INSERT OR IGNORE INTO admins VALUES(?,?,1,?)",(OWNER_ID,"owner",now()))
def event(uid,txt):
    with connect() as c: c.execute("INSERT INTO events(actor,event,created) VALUES(?,?,?)",(uid,txt,now()))
def admin(uid):
    with connect() as c: r=c.execute("SELECT active FROM admins WHERE uid=?",(uid,)).fetchone()
    return bool(r and r[0])
def owner(uid):
    with connect() as c: r=c.execute("SELECT role FROM admins WHERE uid=? AND active=1",(uid,)).fetchone()
    return bool(r and r[0]=="owner")
def keyboard(uid):
    b=InlineKeyboardBuilder(); b.button(text="🎫 ثبت تیکت",callback_data="ticket")
    if admin(uid):
        b.button(text="📊 آمار",callback_data="stats"); b.button(text="🧪 شبیه‌سازی",callback_data="demo"); b.button(text="📨 تیکت‌های باز",callback_data="tickets")
    if owner(uid): b.button(text="👥 مدیران",callback_data="admins")
    b.adjust(1); return b.as_markup()

@dp.message(CommandStart())
async def start(m:Message):
    await m.answer("🦊 FOX REPORTER PRO\\n\\nپنل مدیریت تیکت و دسترسی‌ها با شبیه‌ساز محلی. این نسخه ریپورت خودکار انجام نمی‌دهد و سشن یا کد ورود جمع‌آوری نمی‌کند.",reply_markup=keyboard(m.from_user.id))
@dp.message(Command("help"))
async def help_(m:Message): await m.answer("برای ثبت درخواست، دکمه ثبت تیکت را بزن. مدیران: /addadmin ID ، /deladmin ID ، /reply TICKET_ID متن")
@dp.callback_query(F.data=="ticket")
async def ticket(q:CallbackQuery):
    waiting[q.from_user.id]="ticket"; await q.message.answer("متن درخواستت رو بفرست. رمز، کد ورود یا اطلاعات خصوصی دیگران رو ارسال نکن."); await q.answer()
@dp.callback_query(F.data=="stats")
async def stats(q:CallbackQuery):
    if not admin(q.from_user.id): await q.answer("دسترسی نداری",show_alert=True); return
    with connect() as c:
        t=c.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]; op=c.execute("SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0]
        a=c.execute("SELECT COUNT(*) FROM admins WHERE active=1").fetchone()[0]; d=c.execute("SELECT COUNT(*) FROM demos").fetchone()[0]
    await q.message.answer(f"📊 آمار\\nکل تیکت‌ها: {t}\\nتیکت‌های باز: {op}\\nمدیران فعال: {a}\\nشبیه‌سازی‌ها: {d}"); await q.answer()
@dp.callback_query(F.data=="demo")
async def demo(q:CallbackQuery):
    if not admin(q.from_user.id): await q.answer("دسترسی نداری",show_alert=True); return
    await q.answer(); msg=await q.message.answer("🧪 شبیه‌سازی محلی: 0%")
    for p in (20,40,60,80,100):
        await asyncio.sleep(1)
        try: await msg.edit_text(f"🧪 شبیه‌سازی محلی: {p}%")
        except TelegramBadRequest: pass
    with connect() as c: c.execute("INSERT INTO demos(actor,created) VALUES(?,?)",(q.from_user.id,now()))
    event(q.from_user.id,"completed demo")
@dp.callback_query(F.data=="tickets")
async def tickets(q:CallbackQuery):
    if not admin(q.from_user.id): await q.answer("دسترسی نداری",show_alert=True); return
    with connect() as c: rows=c.execute("SELECT id,uid,body FROM tickets WHERE status='open' ORDER BY id DESC LIMIT 10").fetchall()
    if not rows: await q.message.answer("تیکت بازی نیست.")
    for tid,uid,body in rows: await q.message.answer(f"🎫 #{tid} از {uid}\\n{body[:2500]}\\n\\nپاسخ: /reply {tid} متن")
    await q.answer()
@dp.callback_query(F.data=="admins")
async def admins(q:CallbackQuery):
    if not owner(q.from_user.id): await q.answer("فقط مالک",show_alert=True); return
    with connect() as c: rows=c.execute("SELECT uid,role,active FROM admins ORDER BY role,uid").fetchall()
    await q.message.answer("👥 مدیران\\n"+"\\n".join(f"{u} | {r} | {'فعال' if a else 'غیرفعال'}" for u,r,a in rows)+"\\n\\n/addadmin ID\\n/deladmin ID"); await q.answer()
@dp.message(Command("addadmin"))
async def addadmin(m:Message):
    if not owner(m.from_user.id): return
    p=(m.text or "").split()
    if len(p)!=2 or not p[1].isdigit(): await m.answer("فرمت: /addadmin شناسه"); return
    uid=int(p[1])
    with connect() as c: c.execute("INSERT INTO admins VALUES(?,?,1,?) ON CONFLICT(uid) DO UPDATE SET role='admin',active=1",(uid,"admin",now()))
    event(m.from_user.id,f"added admin {uid}"); await m.answer("مدیر اضافه شد.")
@dp.message(Command("deladmin"))
async def deladmin(m:Message):
    if not owner(m.from_user.id):
        return
    p=(m.text or "").split()
    if len(p)!=2 or not p[1].isdigit(): await m.answer("فرمت: /deladmin شناسه"); return
    uid=int(p[1])
    if uid==OWNER_ID: await m.answer("مالک اصلی قابل حذف نیست."); return
    with connect() as c: c.execute("UPDATE admins SET active=0 WHERE uid=? AND role!='owner'",(uid,))
    event(m.from_user.id,f"disabled admin {uid}"); await m.answer("دسترسی غیرفعال شد.")
@dp.message(Command("reply"))
async def reply(m:Message,bot:Bot):
    if not admin(m.from_user.id): return
    p=(m.text or "").split(maxsplit=2)
    if len(p)<3 or not p[1].isdigit(): await m.answer("فرمت: /reply شماره متن پاسخ"); return
    tid,txt=int(p[1]),p[2]
    with connect() as c:
        r=c.execute("SELECT uid FROM tickets WHERE id=?",(tid,)).fetchone()
        if r: c.execute("UPDATE tickets SET status='closed',reply=? WHERE id=?",(txt,tid))
    if not r: await m.answer("تیکت پیدا نشد."); return
    try: await bot.send_message(r[0],f"📩 پاسخ تیکت #{tid}:\\n{txt}"); await m.answer("پاسخ ارسال شد و تیکت بسته شد.")
    except Exception: await m.answer("پاسخ ذخیره شد؛ ارسال پیام به کاربر ناموفق بود.")
    event(m.from_user.id,f"replied ticket {tid}")
@dp.message()
async def incoming(m:Message):
    if waiting.pop(m.from_user.id,None)=="ticket":
        body=(m.text or "").strip()
        if len(body)<5 or len(body)>3000: await m.answer("متن باید بین ۵ تا ۳۰۰۰ نویسه باشد. دوباره تیکت را بزن."); return
        with connect() as c:
            cur=c.execute("INSERT INTO tickets(uid,username,body,created) VALUES(?,?,?,?)",(m.from_user.id,m.from_user.username,body,now())); tid=cur.lastrowid
        event(m.from_user.id,f"created ticket {tid}"); await m.answer(f"✅ تیکت #{tid} ثبت شد.")
        try: await m.bot.send_message(OWNER_ID,f"🎫 تیکت جدید #{tid} از {m.from_user.id}\\n\\n{body[:2500]}")
        except Exception: logging.exception("owner notification failed")
    else: await m.answer("برای شروع /start را بزن.")
async def main():
    if not TOKEN: raise RuntimeError("BOT_TOKEN تنظیم نشده است.")
    if OWNER_ID<=0: raise RuntimeError("OWNER_ID باید شناسه عددی معتبر باشد.")
    init(); await dp.start_polling(Bot(TOKEN))
if __name__=="__main__": asyncio.run(main())
