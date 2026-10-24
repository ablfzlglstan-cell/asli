import os, sqlite3, logging, json, urllib.request, asyncio, math
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton as B, InlineKeyboardMarkup as K
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN=os.getenv('BOT_TOKEN','').strip()
ADMINS={int(x) for x in os.getenv('ADMIN_IDS','').split(',') if x.strip().isdigit()}
DB=os.getenv('DB_PATH','vynexa_stars.sqlite3'); CARD=os.getenv('CARD_NUMBER','شماره کارت را در تنظیمات وارد کنید'); HOLDER=os.getenv('CARD_HOLDER','نام صاحب کارت را در تنظیمات وارد کنید'); SUPPORT=os.getenv('SUPPORT_USERNAME','fbugtjng').lstrip('@'); CUR=os.getenv('CURRENCY','ریال'); MIN_TOPUP=int(os.getenv('MIN_WALLET_TOPUP','100000')); EMOJI=os.getenv('CUSTOM_EMOJI','').strip()
PREM={k:float(os.getenv('PRICE_PREMIUM_'+k+'M','0')) for k in ('3','6','12')}; STARS={k:float(os.getenv('PRICE_STARS_'+k,'0')) for k in ('50','100','250','500','1000')}
logging.basicConfig(level=logging.INFO)
def now(): return datetime.now(timezone.utc).isoformat()
def money(n): return f'{int(n):,} {CUR}'
def ton_fmt(n): return f'{float(n):g} TON'
def get_ton_rate_sync():
    # CoinGecko market quote; this is a market reference, not a guaranteed local cash-exchange rate.
    req=urllib.request.Request('https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=irr',headers={'User-Agent':'VynexaStars/1.0'})
    with urllib.request.urlopen(req,timeout=5) as r: data=json.loads(r.read().decode())
    rate=float(data['the-open-network']['irr'])
    if rate <= 0: raise ValueError('bad TON rate')
    return int(rate)
async def ton_rate():
    try:
        rate=await asyncio.to_thread(get_ton_rate_sync)
        set_setting('ton_rate_irr',rate); set_setting('ton_rate_at',now())
        return rate, True
    except Exception:
        cached=setting('ton_rate_irr','0')
        return (int(cached),False) if cached.isdigit() and int(cached)>0 else (0,False)
def toman(irr): return f'{int(round(irr/10)):,} تومان'
def rial(irr): return f'{int(round(irr)):,} ریال'
def product_total(ton, rate): return int(math.ceil(float(ton)*rate))
def con():
 c=sqlite3.connect(DB,timeout=20); c.row_factory=sqlite3.Row; return c
def init():
 with con() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(uid INTEGER PRIMARY KEY,username TEXT,first_name TEXT,balance INTEGER DEFAULT 0,created TEXT); CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,uid INTEGER,kind TEXT,pkey TEXT,title TEXT,amount INTEGER,method TEXT,status TEXT,receipt TEXT,created TEXT, recipient TEXT DEFAULT ''); CREATE TABLE IF NOT EXISTS wallet(id INTEGER PRIMARY KEY AUTOINCREMENT,uid INTEGER,amount INTEGER,status TEXT,receipt TEXT,created TEXT); CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
  cols={r['name'] for r in c.execute('PRAGMA table_info(orders)').fetchall()}
  if 'recipient' not in cols: c.execute("ALTER TABLE orders ADD COLUMN recipient TEXT DEFAULT ''")
  if 'ton_amount' not in cols: c.execute("ALTER TABLE orders ADD COLUMN ton_amount REAL DEFAULT 0")
  if 'ton_rate' not in cols: c.execute("ALTER TABLE orders ADD COLUMN ton_rate INTEGER DEFAULT 0")
  for k,v in [('link1_title','کانال وینکسا'),('link1_url','https://t.me/VynexaVPN'),('link2_title','ربات وینکسا'),('link2_url','https://t.me/VynexaVPN_bot'),('link3_title','کانال سوم'),('link3_url','https://t.me/'),('link4_title','ربات چهارم'),('link4_url','https://t.me/'),('emoji_stars','⭐'),('emoji_premium','💎'),('emoji_wallet','👛'),('emoji_orders','🧾'),('emoji_links','🌐'),('emoji_support','📞'),('emoji_admin','🛠'),('ton_rate_irr','0'),('ton_rate_at','')]: c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(k,v))
def setting(key, default=''):
 with con() as c:
  r=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone(); return r['value'] if r else default
def set_setting(key,value):
 with con() as c: c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,str(value)))
def ensure(u):
 with con() as c: c.execute('INSERT INTO users VALUES(?,?,?,0,?) ON CONFLICT(uid) DO UPDATE SET username=excluded.username,first_name=excluded.first_name',(u.id,u.username or '',u.first_name or '',now()))
def bal(uid):
 with con() as c:
  r=c.execute('SELECT balance FROM users WHERE uid=?',(uid,)).fetchone(); return r['balance'] if r else 0
def b(text,data,style=None):
 a={'text':text,'callback_data':data}
 if style:a['style']=style
 if EMOJI:a['icon_custom_emoji_id']=EMOJI
 try:return B(**a)
 except TypeError:a.pop('style',None);a.pop('icon_custom_emoji_id',None);return B(**a)
def menu(uid):
 rows=[[b(f"{setting('emoji_stars','⭐')} خرید استارز",'buy:stars','success'),b(f"{setting('emoji_premium','💎')} خرید پریمیوم",'buy:premium','primary')],[b(f"{setting('emoji_wallet','👛')} کیف پول",'wallet'),b(f"{setting('emoji_orders','🧾')} سفارش‌های من",'orders')],[b(f"{setting('emoji_links','🌐')} کانال ها و ربات های ما",'ourlinks')],[b(f"{setting('emoji_support','📞')} پشتیبانی",'support')]]
 if uid in ADMINS: rows.append([b(f"{setting('emoji_admin','🛠')} پنل مدیریت",'admin','danger')])
 return K(rows)
def links_menu():
 rows=[]
 for i in range(1,5):
  title=setting(f'link{i}_title',f'لینک {i}'); url=setting(f'link{i}_url','')
  if url and url.startswith(('https://','http://','tg://')): rows.append([B(text=title,url=url)])
 rows.append([b('⬅️ بازگشت','home')]); return K(rows)
def product_menu(kind):
 data=PREM if kind=='premium' else STARS; labels={'3':'پریمیوم ۳ ماهه','6':'پریمیوم ۶ ماهه','12':'پریمیوم ۱۲ ماهه'}
 return K([[b(f"{labels.get(k,k+' استارز')} — {ton_fmt(v) if v>0 else 'قیمت تنظیم نشده'}",f'product:{kind}:{k}')] for k,v in data.items()]+[[b('⬅️ بازگشت','home')]])
async def edit(q,text,markup=None,pm=None):
 try: await q.edit_message_text(text,reply_markup=markup,parse_mode=pm,disable_web_page_preview=True)
 except TelegramError: await q.message.reply_text(text,reply_markup=markup,parse_mode=pm)
async def notify(ctx,uid,text,markup=None):
 try: await ctx.bot.send_message(uid,text,reply_markup=markup)
 except TelegramError: pass
async def admins(ctx,text,markup=None):
 for aid in ADMINS: await notify(ctx,aid,text,markup)
def order_buttons(oid): return K([[b('✅ تأیید پرداخت',f'approve:{oid}','success'),b('❌ رد سفارش',f'reject:{oid}','danger')],[b('🎉 ثبت تحویل',f'delivered:{oid}','primary')]])
async def start(up,ctx):
 ensure(up.effective_user); await up.effective_message.reply_text('✨ <b>به Vynexa Stars خوش اومدی</b>\n\nدنیای بدون مرز 💙\nاز منو استارز یا پریمیوم سفارش بده.',reply_markup=menu(up.effective_user.id),parse_mode=ParseMode.HTML)
async def payment_choice(q,p,recipient):
 rate,live=await ton_rate(); rate_line=(f'1 TON = {rial(rate)}' if rate else 'نرخ TON موقتاً در دسترس نیست')
 await edit(q,f'🧾 <b>تأیید سفارش</b>\nمحصول: {p["title"]}\nگیرنده: <code>{recipient}</code>\nقیمت: <b>{ton_fmt(p["ton_amount"])}</b>\n{rate_line}\nمبلغ قابل پرداخت: <b>{rial(p["amount"])}</b> ({toman(p["amount"])})\n\nنرخ بازار ممکن است با نرخ صرافی محلی تفاوت داشته باشد.\n\nاگر اطلاعات درسته، روش پرداخت رو انتخاب کن:',K([[b('💳 کارت‌به‌کارت','pay:card','primary')],[b('👛 کیف پول','pay:wallet','success')],[b('✏️ تغییر گیرنده','recipient:other')],[b('❌ لغو','home')]]),ParseMode.HTML)
async def cb(up,ctx):
 q=up.callback_query; await q.answer(); u=up.effective_user; ensure(u); d=q.data
 if d=='home': ctx.user_data.pop('product',None); await edit(q,'✨ <b>Vynexa Stars</b>\nچه کاری برات انجام بدم؟',menu(u.id),ParseMode.HTML)
 elif d.startswith('buy:'):
  rate,live=await ton_rate(); stamp=setting('ton_rate_at','')
  info=(f'\n1 TON = {rial(rate)}' + ('' if live else ' (آخرین نرخ ذخیره‌شده)')) if rate else '\nنرخ TON فعلاً در دسترس نیست.'
  await edit(q,'بسته موردنظرت رو انتخاب کن:'+info,product_menu(d.split(':')[1]))
 elif d.startswith('product:'):
  _,kind,key=d.split(':'); price=(PREM if kind=='premium' else STARS)[key]
  if price<=0: await q.answer('قیمت TON این محصول هنوز تنظیم نشده.',show_alert=True); return
  rate,live=await ton_rate()
  if rate<=0: await q.answer('نرخ لحظه‌ای TON فعلاً در دسترس نیست؛ کمی بعد تلاش کن.',show_alert=True); return
  title=({'3':'پریمیوم ۳ ماهه','6':'پریمیوم ۶ ماهه','12':'پریمیوم ۱۲ ماهه'}[key] if kind=='premium' else key+' استارز'); ctx.user_data['product']={'kind':kind,'key':key,'title':title,'ton_amount':price,'rate':rate,'amount':product_total(price,rate)}
  await edit(q,f'🎯 <b>برای چه کسی سفارش می‌دی؟</b>\n\nمحصول: {title}\nقیمت: <b>{ton_fmt(price)}</b>\n1 TON = {rial(rate)}\nمبلغ تقریبی: <b>{rial(product_total(price,rate))}</b> ({toman(product_total(price,rate))})',K([[b('🙋 برای خودم','recipient:self','success')],[b('🎁 برای شخص دیگر','recipient:other','primary')],[b('⬅️ بازگشت','buy:'+kind)]]),ParseMode.HTML)
 elif d=='recipient:self':
  p=ctx.user_data.get('product')
  if not p: await edit(q,'از منو محصول رو انتخاب کن.',menu(u.id)); return
  ctx.user_data['recipient']=f"@{u.username} (ID: {u.id})" if u.username else f'ID: {u.id}'
  await payment_choice(q,p,ctx.user_data['recipient'])
 elif d=='recipient:other':
  if not ctx.user_data.get('product'): await edit(q,'از منو محصول رو انتخاب کن.',menu(u.id)); return
  ctx.user_data['await_recipient']=True; await edit(q,'آیدی یا نام کاربری تلگرام گیرنده رو بفرست؛ مثلاً @username یا عددی مثل 123456789.\n\nتوجه: برای نمایش اطلاعات خصوصی حساب‌ها دسترسی نداریم؛ فقط اطلاعات عمومی/آیدی واردشده قابل ثبت است.',K([[b('⬅️ بازگشت','home')]]))
 elif d=='recipient:confirm':
  p=ctx.user_data.get('product'); rec=ctx.user_data.get('recipient','')
  if not p or not rec: await edit(q,'اطلاعات سفارش منقضی شده؛ دوباره شروع کن.',menu(u.id)); return
  await payment_choice(q,p,rec)
 elif d=='ourlinks': await edit(q,'🌐 <b>کانال ها و ربات های ما</b>\nیکی از گزینه‌ها رو انتخاب کن:',links_menu(),ParseMode.HTML)
 elif d.startswith('pay:'):
  p=ctx.user_data.get('product')
  if not p: await edit(q,'از منو دوباره محصول رو انتخاب کن.',menu(u.id)); return
  method=d.split(':')[1]
  if method=='wallet' and bal(u.id)<p['amount']: await edit(q,f'موجودی کافی نیست.\nموجودی: {money(bal(u.id))}\nمبلغ سفارش: {money(p["amount"])}',K([[b('➕ افزایش موجودی','wallet:add')],[b('⬅️ منو','home')]])); return
  with con() as c:
   oid=c.execute('INSERT INTO orders(uid,kind,pkey,title,amount,method,status,created,recipient,ton_amount,ton_rate) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(u.id,p['kind'],p['key'],p['title'],p['amount'],method,'awaiting_receipt' if method=='card' else 'paid_pending_delivery',now(),ctx.user_data.get('recipient',''),p['ton_amount'],p['rate'])).lastrowid
   if method=='wallet' and not c.execute('UPDATE users SET balance=balance-? WHERE uid=? AND balance>=?',(p['amount'],u.id,p['amount'])).rowcount: c.execute('DELETE FROM orders WHERE id=?',(oid,)); await edit(q,'موجودی کافی نیست.',menu(u.id)); return
  ctx.user_data.pop('product',None); recipient=ctx.user_data.pop('recipient','')
  ton_price=ton_fmt(p['ton_amount']); rate_text=rial(p['rate']); amount_text=rial(p['amount']); amount_toman=toman(p['amount'])
  if method=='card':
   ctx.user_data['receipt_order']=oid; await edit(q,f'💳 <b>سفارش #{oid}</b>\nمحصول: {p["title"]}\nقیمت: <b>{ton_price}</b>\n1 TON = {rate_text}\nمبلغ قابل پرداخت: <b>{amount_text}</b> ({amount_toman})\n\nصاحب کارت: <b>{HOLDER}</b>\nشماره کارت: <code>{CARD}</code>\n\nگیرنده: <code>{recipient}</code>\n\nبعد از واریز، عکس رسید رو همین‌جا بفرست.',K([[b('🏠 منو','home')]]),ParseMode.HTML)
  else: await edit(q,f'سفارش #{oid} ثبت شد و برای تحویل منتظر بررسی مدیر است.',K([[b('🧾 سفارش‌ها','orders'),b('🏠 منو','home')]])); await admins(ctx,f'👛 سفارش #{oid}\nکاربر: {u.id}\nمحصول: {p["title"]}\nگیرنده: {recipient}\nقیمت TON: {ton_price}\nنرخ ثبت‌شده: {rate_text}\nمبلغ: {amount_text}',order_buttons(oid))
 elif d=='wallet': await edit(q,f'👛 <b>کیف پول</b>\nموجودی: <b>{money(bal(u.id))}</b>',K([[b('➕ افزایش موجودی','wallet:add')],[b('⬅️ منو','home')]]),ParseMode.HTML)
 elif d=='wallet:add': ctx.user_data['wallet_amount']=True; await edit(q,f'مبلغ افزایش موجودی رو به عدد بفرست (حداقل {money(MIN_TOPUP)}).',K([[b('⬅️ بازگشت','wallet')]]))
 elif d=='orders':
  with con() as c: rs=c.execute('SELECT id,title,amount,status FROM orders WHERE uid=? ORDER BY id DESC LIMIT 10',(u.id,)).fetchall()
  names={'awaiting_receipt':'در انتظار رسید','paid_pending_delivery':'در انتظار تحویل','delivered':'تحویل‌شده','rejected':'ردشده'}; text='🧾 <b>سفارش‌های من</b>\n\n'+('\n\n'.join(f"#{r['id']} · {r['title']} · {rial(r['amount'])} ({toman(r['amount'])})\nوضعیت: {names.get(r['status'],r['status'])}" for r in rs) if rs else 'هنوز سفارشی نداری.')
  await edit(q,text,K([[b('⬅️ منو','home')]]),ParseMode.HTML)
 elif d=='support': await edit(q,f'📞 پشتیبانی: @{SUPPORT}',K([[b('⬅️ منو','home')]]))
 elif d=='admin':
  if u.id not in ADMINS:return
  with con() as c: n=c.execute("SELECT COUNT(*) n FROM orders WHERE status IN ('awaiting_receipt','paid_pending_delivery')").fetchone()['n']; w=c.execute("SELECT COUNT(*) n FROM wallet WHERE status='pending'").fetchone()['n']
  await edit(q,f'🛠 <b>پنل مدیریت</b>\nسفارش‌های در انتظار: {n}\nدرخواست‌های کیف پول: {w}',K([[b('📋 سفارش‌های در انتظار','adm:orders')],[b('👛 درخواست‌های کیف پول','adm:wallets')],[b('💰 ویرایش قیمت','adm:price')],[b('🌐 تنظیم کانال‌ها و ربات‌ها','adm:links')],[b('🎨 تغییر ایموجی دکمه‌ها','adm:emoji')],[b('⬅️ منو','home')]]),ParseMode.HTML)
 elif d=='adm:price':
  if u.id not in ADMINS:return
  ctx.user_data['admin_setting_mode']='price'; await edit(q,'قیمت هر محصول را بر حسب TON وارد کن؛ اعشاری هم مجاز است. نمونه:\nPRICE_PREMIUM_3M=2\nPRICE_STARS_100=0.5\n\nقیمت‌ها پس از ذخیره در فاکتور با نرخ لحظه‌ای TON به ریال تبدیل می‌شوند.',K([[b('⬅️ پنل','admin')]]))
 elif d=='adm:links':
  if u.id not in ADMINS:return
  ctx.user_data['admin_setting_mode']='links'; await edit(q,'برای تغییر هر لینک، یک خط با قالب زیر بفرست (چهار لینک قابل تنظیم است):\n1|عنوان|https://t.me/example\n2|عنوان|https://t.me/example\n3|عنوان|https://t.me/example\n4|عنوان|https://t.me/example',K([[b('⬅️ پنل','admin')]]))
 elif d=='adm:emoji':
  if u.id not in ADMINS:return
  ctx.user_data['admin_setting_mode']='emoji'; await edit(q,'اول مشخص کن ایموجی کدام دکمه را عوض کنیم:',K([[b('⭐ خرید استارز','emojitarget:stars')],[b('💎 خرید پریمیوم','emojitarget:premium')],[b('👛 کیف پول','emojitarget:wallet')],[b('🧾 سفارش‌ها','emojitarget:orders')],[b('🌐 کانال‌ها و ربات‌ها','emojitarget:links')],[b('📞 پشتیبانی','emojitarget:support')],[b('🛠 پنل مدیریت','emojitarget:admin')],[b('⬅️ پنل','admin')]]))
 elif d.startswith('emojitarget:'):
  if u.id not in ADMINS:return
  target=d.split(':',1)[1]; ctx.user_data['emoji_target']=target; ctx.user_data['admin_setting_mode']='emoji_one'; await edit(q,f'ایموجی جدید برای «{target}» را در یک پیام بفرست. (می‌توانی ایموجی معمولی یا custom emoji تلگرام بفرستی.)',K([[b('⬅️ انتخاب دکمه','adm:emoji')]]))
 elif d=='adm:orders':
  if u.id not in ADMINS:return
  with con() as c: rs=c.execute("SELECT id,uid,title,amount,status FROM orders WHERE status IN ('awaiting_receipt','paid_pending_delivery') ORDER BY id DESC LIMIT 20").fetchall()
  await edit(q,'📋 سفارش‌های در انتظار\n\n'+('\n'.join(f"#{r['id']} · کاربر {r['uid']} · {r['title']} · {rial(r['amount'])} ({toman(r['amount'])})" for r in rs) if rs else 'موردی نیست.'),K([[b(f"باز کردن #{r['id']}",f"adm:order:{r['id']}")] for r in rs]+[[b('⬅️ پنل','admin')]]))
 elif d.startswith('adm:order:'):
  if u.id not in ADMINS:return
  oid=int(d.rsplit(':',1)[1])
  with con() as c: r=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
  if r: await edit(q,f"سفارش #{oid}\nکاربر: {r['uid']}\nمحصول: {r['title']}\nگیرنده: {r['recipient']}\nمبلغ: {rial(r['amount'])} ({toman(r['amount'])})\nقیمت TON: {ton_fmt(r['ton_amount'])} | نرخ: {rial(r['ton_rate'])}\nوضعیت: {r['status']}",order_buttons(oid))
 elif d.startswith(('approve:','reject:','delivered:')):
  if u.id not in ADMINS:return
  action,oid_s=d.split(':'); oid=int(oid_s)
  with con() as c: r=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
  if not r:return
  status={'approve':'paid_pending_delivery','reject':'rejected','delivered':'delivered'}[action]
  with con() as c:c.execute('UPDATE orders SET status=? WHERE id=?',(status,oid))
  await notify(ctx,r['uid'],{'approve':f'پرداخت سفارش #{oid} تأیید شد؛ سفارش در صف تحویل است.','reject':f'سفارش #{oid} رد شد؛ برای پیگیری با پشتیبانی تماس بگیر.','delivered':f'🎉 سفارش #{oid} تحویل‌شده ثبت شد.'}[action]); await edit(q,{'approve':'پرداخت تأیید شد.','reject':'سفارش رد شد.','delivered':'تحویل ثبت شد.'}[action],K([[b('⬅️ پنل','admin')]]))
 elif d=='adm:wallets':
  if u.id not in ADMINS:return
  with con() as c: rs=c.execute("SELECT id,uid,amount FROM wallet WHERE status='pending' ORDER BY id DESC LIMIT 20").fetchall()
  await edit(q,'👛 درخواست‌های کیف پول\n\n'+('\n'.join(f"#{r['id']} · کاربر {r['uid']} · {money(r['amount'])}" for r in rs) if rs else 'موردی نیست.'),K([[b(f"بررسی #{r['id']}",f"adm:wallet:{r['id']}")] for r in rs]+[[b('⬅️ پنل','admin')]]))
 elif d.startswith('adm:wallet:'):
  if u.id not in ADMINS:return
  rid=int(d.rsplit(':',1)[1])
  with con() as c:r=c.execute('SELECT * FROM wallet WHERE id=?',(rid,)).fetchone()
  if r: await edit(q,f"درخواست #{rid}\nکاربر: {r['uid']}\nمبلغ: {money(r['amount'])}",K([[b('✅ تأیید و شارژ',f'walletok:{rid}','success'),b('❌ رد',f'walletno:{rid}','danger')]]))
 elif d.startswith(('walletok:','walletno:')):
  if u.id not in ADMINS:return
  action,rid_s=d.split(':'); rid=int(rid_s)
  with con() as c:r=c.execute('SELECT * FROM wallet WHERE id=?',(rid,)).fetchone()
  if not r or r['status']!='pending':await q.answer('قبلاً بررسی شده.',show_alert=True);return
  with con() as c:
   c.execute('UPDATE wallet SET status=? WHERE id=?',('approved' if action=='walletok' else 'rejected',rid))
   if action=='walletok':c.execute('UPDATE users SET balance=balance+? WHERE uid=?',(r['amount'],r['uid']))
  await notify(ctx,r['uid'],'✅ کیف پولت شارژ شد.' if action=='walletok' else '⚠️ درخواست افزایش موجودی رد شد.'); await edit(q,'درخواست بررسی شد.',K([[b('⬅️ پنل','admin')]]))
async def messages(up,ctx):
 u=up.effective_user
 if not u:return
 ensure(u); m=up.effective_message
 if m.text and ctx.user_data.get('await_recipient'):
  rec=m.text.strip(); ctx.user_data['await_recipient']=False
  if not (rec.startswith('@') and len(rec)>1 or rec.isdigit()): ctx.user_data['await_recipient']=True; await m.reply_text('فرمت آیدی درست نیست. @username یا آیدی عددی بفرست.'); return
  ctx.user_data['recipient']=rec; p=ctx.user_data.get('product')
  if not p: await m.reply_text('سفارش پیدا نشد؛ /start رو بزن.'); return
  await m.reply_text(f'🔎 گیرنده: {rec}\n\nربات نمی‌تونه اطلاعات خصوصی یا جزئیات کامل حساب کاربر رو از روی آیدی واکشی کنه. بررسی کن آیدی درست باشه و تأیید رو بزن.',reply_markup=K([[b('✅ تأیید گیرنده','recipient:confirm')],[b('✏️ وارد کردن دوباره','recipient:other')],[b('❌ لغو','home')]])); return
 if ctx.user_data.get('admin_setting_mode')=='emoji_one' and u.id in ADMINS and (m.text or m.entities):
  target=ctx.user_data.pop('emoji_target',None); ctx.user_data.pop('admin_setting_mode',None); mp={'stars':'emoji_stars','premium':'emoji_premium','wallet':'emoji_wallet','orders':'emoji_orders','links':'emoji_links','support':'emoji_support','admin':'emoji_admin'}
  value=(m.text or m.caption or '').strip()
  if target in mp and value:
   set_setting(mp[target],value[:16]); await m.reply_text('✅ ایموجی ذخیره شد. منوی جدید را از /start باز کن تا تغییر را ببینی.',reply_markup=menu(u.id))
  else: await m.reply_text('ایموجی متنی دریافت نشد؛ دوباره از پنل انتخاب کن.')
  return
 if m.text and ctx.user_data.get('admin_setting_mode') and u.id in ADMINS:
  mode=ctx.user_data.pop('admin_setting_mode'); lines=m.text.splitlines(); ok=0
  try:
   if mode=='price':
    for line in lines:
     if '=' not in line: continue
     key,val=line.split('=',1); key=key.strip(); val=val.strip()
     if key in {'PRICE_PREMIUM_3M','PRICE_PREMIUM_6M','PRICE_PREMIUM_12M','PRICE_STARS_50','PRICE_STARS_100','PRICE_STARS_250','PRICE_STARS_500','PRICE_STARS_1000'}:
      try:
       num=float(val.replace(',','.'))
       if num>0: set_setting(key,num); ok+=1
      except ValueError: pass
    # values persist in DB and update active dictionaries
    for k in ('3','6','12'): PREM[k]=float(setting('PRICE_PREMIUM_'+k+'M',str(PREM[k])))
    for k in ('50','100','250','500','1000'): STARS[k]=float(setting('PRICE_STARS_'+k,str(STARS[k])))
   elif mode=='links':
    for line in lines:
     parts=line.split('|',2)
     if len(parts)==3 and parts[0].strip() in ('1','2','3','4') and parts[2].strip().startswith(('https://','http://','tg://')):
      i=parts[0].strip(); set_setting('link'+i+'_title',parts[1].strip()[:60]); set_setting('link'+i+'_url',parts[2].strip()); ok+=1
   elif mode=='emoji':
    mp={'stars':'emoji_stars','premium':'emoji_premium','wallet':'emoji_wallet','orders':'emoji_orders','links':'emoji_links','support':'emoji_support','admin':'emoji_admin'}
    for line in lines:
     if '=' in line:
      k,v=line.split('=',1); k=k.strip(); v=v.strip()
      if k in mp and v: set_setting(mp[k],v[:16]); ok+=1
   await m.reply_text(f'✅ تنظیمات ذخیره شد. موارد تغییرکرده: {ok}',reply_markup=menu(u.id))
  except Exception as e: logging.exception('settings update failed'); await m.reply_text('ذخیره تنظیمات ناموفق بود. دوباره امتحان کن.')
  return
 if ctx.user_data.get('wallet_amount') and m.text:
  raw=m.text.replace(',','').replace('٬','').strip()
  if not raw.isdigit() or int(raw)<MIN_TOPUP:await m.reply_text(f'مبلغ معتبر وارد کن؛ حداقل {money(MIN_TOPUP)}.');return
  amount=int(raw);ctx.user_data['wallet_amount']=False
  with con() as c:rid=c.execute("INSERT INTO wallet(uid,amount,status,created) VALUES(?,?,'awaiting_receipt',?)",(u.id,amount,now())).lastrowid
  ctx.user_data['wallet_receipt']=rid;await m.reply_text(f'درخواست افزایش موجودی #{rid}\nمبلغ: {money(amount)}\nصاحب کارت: {HOLDER}\nشماره کارت: {CARD}\nبعد از پرداخت عکس رسید رو بفرست.');return
 if m.photo:
  fid=m.photo[-1].file_id;oid=ctx.user_data.get('receipt_order');rid=ctx.user_data.get('wallet_receipt')
  if oid:
   with con() as c:r=c.execute('SELECT * FROM orders WHERE id=? AND uid=?',(oid,u.id)).fetchone()
   if r and r['status']=='awaiting_receipt':
    with con() as c:c.execute('UPDATE orders SET receipt=? WHERE id=?',(fid,oid))
    await m.reply_text(f'✅ رسید سفارش #{oid} دریافت شد.')
    await admins(ctx,f"💳 رسید سفارش #{oid}\nکاربر: {u.id}\nمحصول: {r['title']}\nگیرنده: {r['recipient']}\nمبلغ: {money(r['amount'])}",order_buttons(oid))
    for aid in ADMINS:
     try:await ctx.bot.send_photo(aid,fid,caption=f'رسید سفارش #{oid} | کاربر {u.id}')
     except TelegramError:pass
    ctx.user_data.pop('receipt_order',None);return
  if rid:
   with con() as c:r=c.execute('SELECT * FROM wallet WHERE id=? AND uid=?',(rid,u.id)).fetchone()
   if r and r['status']=='awaiting_receipt':
    with con() as c:c.execute("UPDATE wallet SET receipt=?,status='pending' WHERE id=?",(fid,rid))
    await m.reply_text(f'✅ رسید افزایش موجودی #{rid} دریافت شد.')
    await admins(ctx,f"👛 رسید افزایش موجودی #{rid}\nکاربر: {u.id}\nمبلغ: {money(r['amount'])}",K([[b('بررسی درخواست',f'adm:wallet:{rid}')]]))
    for aid in ADMINS:
     try:await ctx.bot.send_photo(aid,fid,caption=f'رسید کیف پول #{rid} | کاربر {u.id}')
     except TelegramError:pass
    ctx.user_data.pop('wallet_receipt',None);return
  await m.reply_text('برای این رسید سفارش در انتظاری پیدا نشد. /start')
 elif m.text:await m.reply_text('برای دیدن منو /start رو بزن.',reply_markup=menu(u.id))
async def post_init(app):
 init()
 for k in ('3','6','12'): PREM[k]=float(setting('PRICE_PREMIUM_'+k+'M',str(PREM[k])))
 for k in ('50','100','250','500','1000'): STARS[k]=float(setting('PRICE_STARS_'+k,str(STARS[k])))
 try: await app.bot.set_my_commands([('start','شروع ربات'),('help','راهنما')])
 except TelegramError: pass
 logging.info('Vynexa Stars started')
def main():
 if not TOKEN:raise SystemExit('BOT_TOKEN را در Environment Variables هاست تنظیم کن.')
 app=Application.builder().token(TOKEN).post_init(post_init).concurrent_updates(8).build();app.add_handler(CommandHandler('start',start));app.add_handler(CommandHandler('help',start));app.add_handler(CallbackQueryHandler(cb));app.add_handler(MessageHandler(filters.PHOTO|(filters.TEXT&~filters.COMMAND),messages));app.run_polling(allowed_updates=Update.ALL_TYPES)
if __name__=='__main__':main()
