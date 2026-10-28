import os, sqlite3, logging, json, re, random, urllib.request, asyncio, html
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton as B, InlineKeyboardMarkup as K, ReactionTypeEmoji
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN=os.getenv('BOT_TOKEN','').strip()
ADMINS={int(x) for x in os.getenv('ADMIN_IDS','').split(',') if x.strip().isdigit()}
DB=os.getenv('DB_PATH','vynexa_stars.sqlite3'); CARD=os.getenv('CARD_NUMBER','شماره کارت را در تنظیمات وارد کنید'); HOLDER=os.getenv('CARD_HOLDER','نام صاحب کارت را در تنظیمات وارد کنید'); SUPPORT=os.getenv('SUPPORT_USERNAME','fbugtjng').lstrip('@'); CUR=os.getenv('CURRENCY','تومان'); MIN_TOPUP=int(os.getenv('MIN_WALLET_TOPUP','10000'))
PREM={k:int(os.getenv('PRICE_PREMIUM_'+k+'M','0')) for k in ('3','6','12')}; STARS={k:int(os.getenv('PRICE_STARS_'+k,'0')) for k in ('50','100','250','500','1000')}
logging.basicConfig(level=logging.INFO)
def now(): return datetime.now(timezone.utc).isoformat()
def money(n): return f'{int(n):,} {CUR}'
def con():
 c=sqlite3.connect(DB,timeout=8); c.row_factory=sqlite3.Row; c.execute('PRAGMA busy_timeout=8000'); return c
def init():
 with con() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(uid INTEGER PRIMARY KEY,username TEXT,first_name TEXT,balance INTEGER DEFAULT 0,created TEXT); CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,uid INTEGER,kind TEXT,pkey TEXT,title TEXT,amount INTEGER,method TEXT,status TEXT,receipt TEXT,created TEXT, recipient TEXT DEFAULT ''); CREATE TABLE IF NOT EXISTS wallet(id INTEGER PRIMARY KEY AUTOINCREMENT,uid INTEGER,amount INTEGER,status TEXT,receipt TEXT,created TEXT); CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
  cols={r['name'] for r in c.execute('PRAGMA table_info(orders)').fetchall()}
  if 'recipient' not in cols: c.execute("ALTER TABLE orders ADD COLUMN recipient TEXT DEFAULT ''")
  for k,v in [('link1_title','کانال وینکسا'),('link1_url','https://t.me/VynexaVPN'),('link2_title','ربات وینکسا'),('link2_url','https://t.me/VynexaVPN_bot'),('link3_title','کانال سوم'),('link3_url','https://t.me/'),('link4_title','ربات چهارم'),('link4_url','https://t.me/'),('emoji_stars','⭐'),('emoji_premium','💎'),('emoji_wallet','👛'),('emoji_orders','🧾'),('emoji_links','🌐'),('emoji_support','📞'),('emoji_admin','🛠'),('text_welcome',''),('text_help',''),('text_trust',''),('text_gift',''),('text_boost','')]: c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(k,v))
# Small in-process cache avoids opening/querying SQLite repeatedly while building menus.
_SETTINGS_CACHE = {}
def setting(key, default=''):
 if key in _SETTINGS_CACHE:
  return _SETTINGS_CACHE[key]
 with con() as c:
  r=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
 value = r['value'] if r else default
 _SETTINGS_CACHE[key] = value
 return value
def set_setting(key,value):
 value = str(value)
 with con() as c: c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))
 _SETTINGS_CACHE[key] = value
def ensure(u):
 with con() as c: c.execute('INSERT INTO users VALUES(?,?,?,0,?) ON CONFLICT(uid) DO UPDATE SET username=excluded.username,first_name=excluded.first_name',(u.id,u.username or '',u.first_name or '',now()))
def bal(uid):
 with con() as c:
  r=c.execute('SELECT balance FROM users WHERE uid=?',(uid,)).fetchone(); return r['balance'] if r else 0
# Button-color editor: Telegram supports four button styles (default, primary, success, danger).
COLOR_BUTTONS = [
 ('buy:stars','خرید استارز'), ('buy:premium','خرید پریمیوم'), ('wallet','کیف پول'),
 ('orders','سفارش‌های من'), ('ourlinks','کانال‌ها و ربات‌های ما'), ('feature:gift','گیفت تلگرام'),
 ('feature:boost','بوست چنل'), ('trust','چگونه بهتون اعتماد کنم؟'), ('support','پشتیبانی'),
 ('admin','پنل مدیریت'), ('product_item','بسته‌های محصول (همه محصولات)'), ('stars:custom','استارز دلخواه'),
 ('recipient:self','برای خودم'), ('recipient:other','برای شخص دیگر'), ('recipient:confirm','تأیید گیرنده'),
 ('invoice:confirm','تأیید فاکتور'), ('pay:card','پرداخت کارت‌به‌کارت'), ('pay:wallet','پرداخت با کیف پول'),
 ('wallet:add','افزایش موجودی'), ('home','بازگشت به منو'), ('link1','لینک شماره ۱'), ('link2','لینک شماره ۲'),
 ('link3','لینک شماره ۳'), ('link4','لینک شماره ۴'), ('adm:orders','سفارش‌های در انتظار'),
 ('adm:wallets','درخواست‌های کیف پول'), ('adm:price','ویرایش قیمت'), ('adm:links','تنظیم کانال‌ها و ربات‌ها'),
 ('adm:emoji','تغییر ایموجی دکمه‌ها'), ('adm:texts','ویرایش متن‌ها'), ('adm:colors','ادیت رنگ‌ها'),
 ('adm:pricepick','انتخاب محصول برای قیمت'), ('adm:priceconfirm','تأیید و ذخیره قیمت'),
 ('adm:pricecancel','لغو تغییر قیمت'), ('adm:links_back','بازگشت از تنظیم لینک‌ها'),
 ('adm:textedit','انتخاب متن برای ویرایش'), ('adm:textcancel','لغو ویرایش متن'),
 ('adm:emojipick','انتخاب ایموجی'), ('adm:emojicancel','لغو تغییر ایموجی'),
 ('adm:order','باز کردن سفارش'), ('approve','تأیید پرداخت سفارش'), ('reject','رد سفارش'),
 ('delivered','ثبت تحویل سفارش'), ('walletok','تأیید و شارژ کیف پول'), ('walletno','رد درخواست کیف پول'),
 ('adm:colorpage','صفحه‌بندی فهرست رنگ‌ها'), ('adm:colorpick','انتخاب دکمه برای تغییر رنگ'),
 ('adm:colorset','انتخاب رنگ'), ('cancel','لغو / انصراف'),
]

def button_color_key(data):
 if data.startswith('product:'): return 'product_item'
 for prefix,key in (('adm:pricepick:','adm:pricepick'),('adm:textedit:','adm:textedit'),('adm:emojipick:','adm:emojipick'),('adm:order:','adm:order'),('adm:wallet:','adm:wallet'),('adm:colorpage:','adm:colorpage'),('adm:colorpick:','adm:colorpick'),('approve:','approve'),('reject:','reject'),('delivered:','delivered'),('walletok:','walletok'),('walletno:','walletno')):
  if data.startswith(prefix): return key
 if data in ('adm:pricecancel','adm:textcancel','adm:emojicancel'): return data
 return data

def b(text,data,style=None):
 color = setting('button_color_' + button_color_key(data), '')
 if color:
  style = None if color == 'default' else color
 a={'text':str(text),'callback_data':data}
 match=re.search(r'<tg-emoji\s+emoji-id=["\'](\d+)["\']>(.*?)</tg-emoji>',a['text'],re.S)
 if match:
  a['icon_custom_emoji_id']=match.group(1)
  a['text']=a['text'][:match.start()]+a['text'][match.end():]
 if style:a['style']=style
 try:return B(**a)
 except (TypeError,ValueError):
  a.pop('style',None);a.pop('icon_custom_emoji_id',None)
  a['text']=re.sub(r'<tg-emoji\s+emoji-id=["\']\d+["\']>(.*?)</tg-emoji>',r'\1',a['text'],flags=re.S)
  return B(**a)
def url_button(text,url,key):
 color=setting('button_color_'+key,'')
 style=None if not color or color=='default' else color
 args={'text':str(text),'url':url}
 if style: args['style']=style
 try: return B(**args)
 except (TypeError,ValueError):
  args.pop('style',None); return B(**args)
TON_CACHE = {"value": None, "at": 0}
def _fetch_ton_rate():
    """Read public TON/IRT price from SwapWallet's public market endpoint/page."""
    urls = ["https://swapwallet.app/api/v1/market/prices", "https://swapwallet.app/en/prices"]
    for url in urls:
        try:
            req=urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 VynexaStars/1.0","Accept":"application/json,text/html,*/*"})
            with urllib.request.urlopen(req, timeout=7) as response: body=response.read().decode("utf-8","ignore")
            try:
                data=json.loads(body)
                def walk(x):
                    if isinstance(x,dict):
                        sym=str(x.get("symbol",x.get("code",x.get("ticker","")))).upper()
                        name=str(x.get("name",x.get("asset", ""))).upper()
                        if sym=="TON" or ("TON" in name and "TONCOIN" in name):
                            for k in ("price_irt","price_irr","irt","price_toman","price","last_price","value"):
                                v=x.get(k)
                                if isinstance(v,(int,float)) and v>1000:return float(v)
                        for v in x.values():
                            found=walk(v)
                            if found:return found
                    elif isinstance(x,list):
                        for v in x:
                            found=walk(v)
                            if found:return found
                    return None
                rate=walk(data)
                if rate:return rate
            except Exception: pass
            # Public prices page fallback: isolate TON row and its first IRT amount.
            plain=re.sub(r"<[^>]+>"," ",body,flags=re.S)
            plain=re.sub(r"\s+"," ",plain)
            m=re.search(r"(?:Toncoin|TON)\s*(?:TON)?\s*([0-9][0-9,٬.]*)",plain,re.I)
            if m:
                val=m.group(1).replace(",","").replace("٬","")
                if "." in val and val.count(".")==1 and len(val.split(".")[-1])<=2: val=val.split(".")[0]
                if val.isdigit() and int(val)>1000:return float(val)
        except Exception as e: logging.warning("TON rate source failed (%s): %s",url,str(e)[:120])
    logging.error("TON/IRT rate unavailable: both configured SwapWallet sources failed or returned an unrecognized format; prices will remain at their configured base values")
    return None
async def ton_rate():
    import time
    if TON_CACHE["value"] and time.time()-TON_CACHE["at"]<300:return TON_CACHE["value"]
    rate=await asyncio.to_thread(_fetch_ton_rate)
    if rate:
        TON_CACHE.update(value=float(rate),at=time.time())
        # Initialize reference rates for existing admin prices once, so they remain the baseline.
        with con() as c:
            for kind, prices in (("premium",PREM),("stars",STARS)):
                for key, price in prices.items():
                    rk=f"ton_ref_{kind}_{key}"
                    c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(rk,str(rate)))
    return rate
async def current_price(kind,key):
    base=(PREM if kind=="premium" else STARS)[key]
    rate=await ton_rate()
    if not rate:return base
    ref=float(setting(f"ton_ref_{kind}_{key}",str(rate)) or rate)
    if ref<=0:return base
    # Price floor: a TON price drop never lowers the configured product price.
    # Only a rise above the reference rate can increase the customer price.
    raw=max(base, round(base*rate/ref))
    # نمایش قیمت‌های وابسته به TON با گام ۱۰۰٬۰۰۰ تومان؛ تغییر فقط هنگام عبور از نیمه گام بعدی.
    step=100_000
    return max(step, int((raw + step/2)//step)*step)

def menu(uid):
 rows=[[b(f"{setting('emoji_stars','⭐')} خرید استارز",'buy:stars','success'),b(f"{setting('emoji_premium','💎')} خرید پریمیوم",'buy:premium','primary')],[b(f"{setting('emoji_wallet','👛')} کیف پول",'wallet'),b(f"{setting('emoji_orders','🧾')} سفارش‌های من",'orders')],[b(f"{setting('emoji_links','🌐')} کانال ها و ربات های ما",'ourlinks')],[b('🎁 گیفت تلگرام','feature:gift'),b('🚀 بوست چنل','feature:boost')],[b('🔐 چگونه بهتون اعتماد کنم؟','trust')],[b(f"{setting('emoji_support','📞')} پشتیبانی",'support')]]
 if uid in ADMINS: rows.append([b(f"{setting('emoji_admin','🛠')} پنل مدیریت",'admin','danger')])
 return K(rows)
def links_menu():
 rows=[]
 for i in range(1,5):
  title=setting(f'link{i}_title',f'لینک {i}'); url=setting(f'link{i}_url','')
  if url and url.startswith(('https://','http://','tg://')): rows.append([url_button(title,url,f'link{i}')])
 rows.append([b('⬅️ بازگشت','home')]); return K(rows)
def product_menu(kind):
 data=PREM if kind=='premium' else STARS; labels={'3':'پریمیوم ۳ ماهه','6':'پریمیوم ۶ ماهه','12':'پریمیوم ۱۲ ماهه'}
 rows=[[b(labels.get(k,k+' استارز'),f'product:{kind}:{k}')] for k,v in data.items()]
 if kind=='stars': rows.append([b('✨ استارز دلخواه','stars:custom')])
 rows.append([b('⬅️ بازگشت','home')])
 return K(rows)
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
 ensure(up.effective_user)
 welcome = setting('text_welcome','') or ('✨ <b>به Vynexa Stars خوش اومدی!</b>\n\n'
  'اینجا می‌تونی بسته‌های استارز و تلگرام پریمیوم رو بررسی کنی و سفارشت رو ثبت کنی.\n'
  'قبل از پرداخت، فاکتور و مبلغ نهایی بهت نمایش داده می‌شه تا با خیال راحت بررسیش کنی.\n\n'
  '💙 <b>Vynexa Stars | دنیای بدون مرز</b>\n'
  'برای شروع، یکی از گزینه‌های منو رو انتخاب کن.')
 await up.effective_message.reply_text(welcome,reply_markup=menu(up.effective_user.id),parse_mode=ParseMode.HTML)

async def help_command(up,ctx):
 text=('📘 <b>راهنمای استفاده از Vynexa Stars</b>\n\n'
       '⭐ <b>خرید استارز:</b> وارد این بخش شو، بسته موردنظر را انتخاب کن و قیمت را ببین.\n\n'
       '💎 <b>خرید پریمیوم:</b> مدت ۳، ۶ یا ۱۲ ماه را انتخاب کن؛ قیمت پس از انتخاب محصول نمایش داده می‌شود.\n\n'
       '🙋 <b>برای خودم:</b> سفارش برای حساب خودت ثبت می‌شود.\n'
       '🎁 <b>برای شخص دیگر:</b> آیدی گیرنده را وارد و تأیید کن.\n\n'
       '💳 <b>پرداخت:</b> روش پرداخت را انتخاب کن؛ برای کارت‌به‌کارت، مبلغ و اطلاعات کارت نمایش داده می‌شود و سپس عکس رسید را بفرست.\n'
       '👛 <b>کیف پول:</b> موجودی و درخواست افزایش موجودی از این بخش قابل پیگیری است.\n'
       '🧾 <b>سفارش‌های من:</b> وضعیت سفارش‌های قبلی را می‌بینی.\n'
       '📞 <b>پشتیبانی:</b> برای پیگیری مشکل از این گزینه استفاده کن.\n\n'
       'برای برگشت به منو، دکمه زیر را بزن یا /start را ارسال کن.')
 await up.effective_message.reply_text(text,reply_markup=K([[b('🏠 منوی اصلی','home')]]),parse_mode=ParseMode.HTML,disable_web_page_preview=True)

async def payment_choice(q,p,recipient):
 kind_label = 'تلگرام پریمیوم' if p['kind']=='premium' else 'تلگرام استارز'
 raw = str(recipient or '').strip()
 username_match = re.search(r'@[\w\d_]+', raw)
 id_match = re.search(r'ID:\s*(\d+)', raw, re.I)
 username = username_match.group(0) if username_match else ''
 numeric_id = id_match.group(1) if id_match else ''
 if not username and raw.startswith('ID:'):
  numeric_id = re.sub(r'\D', '', raw)
 invoice = (
  '🧾 <b>فاکتور سفارش</b>\n\n'
  f'🌐 سرویس: {kind_label} ✨\n'
  f'📦 بسته: {html.escape(str(p["title"]))}\n'
  f'👤 گیرنده: {html.escape(username or "ثبت نشده")}\n'
  f'🆔 آیدی عددی: {html.escape(numeric_id or "در دسترس نیست")}\n'
  f'💰 مبلغ: <b>{money(p["amount"])}</b> 💳\n\n'
  '🔎 لطفاً فاکتور را بررسی کن.\n\n'
  '✅ اگر مشخصات و مبلغ درست است، فاکتور را تأیید کن.'
 )
 await edit(q,invoice,K([[b('✅ تأیید فاکتور','invoice:confirm','success')],[b('✏️ تغییر گیرنده','recipient:other')],[b('❌ لغو سفارش','home')]]),ParseMode.HTML)

async def cb(up,ctx):
 q=up.callback_query; await q.answer(); u=up.effective_user; ensure(u); d=q.data
 if d=='home': ctx.user_data.pop('product',None); await edit(q,setting('text_menu_prompt','✨ <b>Vynexa Stars</b>\nچه کاری برات انجام بدم؟'),menu(u.id),ParseMode.HTML)
 elif d.startswith('buy:'): await edit(q,'بسته موردنظرت رو انتخاب کن:',product_menu(d.split(':')[1]))
 elif d=='stars:custom':
  ctx.user_data['await_custom_stars']=True
  await edit(q,'✨ تعداد استارز دلخواهت رو به عدد بفرست (مثلاً 175).',K([[b('⬅️ بازگشت','buy:stars')]]))
 elif d.startswith('product:'):
  _,kind,key=d.split(':'); price=await current_price(kind,key)
  if price<=0: await q.answer('قیمت این محصول هنوز تنظیم نشده.',show_alert=True); return
  title=({'3':'پریمیوم ۳ ماهه','6':'پریمیوم ۶ ماهه','12':'پریمیوم ۱۲ ماهه'}[key] if kind=='premium' else key+' استارز'); ctx.user_data['product']={'kind':kind,'key':key,'title':title,'amount':price}
  await edit(q,f'🎯 <b>برای چه کسی سفارش می‌دی؟</b>\n\nمحصول: {title}\nمبلغ: <b>{money(price)}</b>',K([[b('🙋 برای خودم','recipient:self','success')],[b('🎁 برای شخص دیگر','recipient:other','primary')],[b('⬅️ بازگشت','buy:'+kind)]]),ParseMode.HTML)
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
 elif d=='trust':
  await edit(q,setting('text_trust','') or ('🔐 <b>چطور می‌تونی به ما اعتماد کنی؟</b>\n\n'
   'برای آشنایی بیشتر با فعالیت‌های وینکسا، وارد بخش «کانال‌ها و ربات‌های ما» شو و کانال‌ها و ربات‌های معرفی‌شده رو بررسی کن.\n\n'
   '💬 اگر سؤالی داشتی، قبل از پرداخت از پشتیبانی بپرس و همیشه مشخصات و مبلغ فاکتور رو با دقت بررسی کن.'),
   K([[b('🌐 کانال‌ها و ربات‌های ما','ourlinks')],[b('📞 پشتیبانی','support')],[b('⬅️ منو','home')]]),ParseMode.HTML)
 elif d=='invoice:confirm':
  p=ctx.user_data.get('product'); recipient=ctx.user_data.get('recipient','')
  if not p or not recipient:
   await edit(q,'اطلاعات سفارش منقضی شده؛ لطفاً دوباره محصول رو انتخاب کن.',menu(u.id)); return
  await edit(q,'💳 <b>روش پرداخت رو انتخاب کن</b>',K([[b('💳 کارت‌به‌کارت','pay:card','primary')],[b('👛 کیف پول','pay:wallet','success')],[b('⬅️ بازگشت به فاکتور','recipient:confirm')],[b('❌ لغو سفارش','home')]]),ParseMode.HTML)
 elif d.startswith('pay:'):
  p=ctx.user_data.get('product')
  if not p: await edit(q,'از منو دوباره محصول رو انتخاب کن.',menu(u.id)); return
  method=d.split(':')[1]
  if method=='wallet' and bal(u.id)<p['amount']: await edit(q,f'موجودی کافی نیست.\nموجودی: {money(bal(u.id))}\nمبلغ سفارش: {money(p["amount"])}',K([[b('➕ افزایش موجودی','wallet:add')],[b('⬅️ منو','home')]])); return
  with con() as c:
   oid=c.execute('INSERT INTO orders(uid,kind,pkey,title,amount,method,status,created,recipient) VALUES(?,?,?,?,?,?,?,?,?)',(u.id,p['kind'],p['key'],p['title'],p['amount'],method,'awaiting_receipt' if method=='card' else 'paid_pending_delivery',now(),ctx.user_data.get('recipient',''))).lastrowid
   if method=='wallet' and not c.execute('UPDATE users SET balance=balance-? WHERE uid=? AND balance>=?',(p['amount'],u.id,p['amount'])).rowcount: c.execute('DELETE FROM orders WHERE id=?',(oid,)); await edit(q,'موجودی کافی نیست.',menu(u.id)); return
  ctx.user_data.pop('product',None); recipient=ctx.user_data.pop('recipient','')
  if method=='card':
   ctx.user_data['receipt_order']=oid; await edit(q,f'💳 <b>سفارش #{oid}</b>\nمحصول: {p["title"]}\nمبلغ: <b>{money(p["amount"])}</b>\n\nصاحب کارت: <b>{HOLDER}</b>\nشماره کارت: <code>{CARD}</code>\n\nگیرنده: <code>{recipient}</code>\n\nبعد از واریز، عکس رسید رو همین‌جا بفرست.',K([[b('🏠 منو','home')]]),ParseMode.HTML)
  else: await edit(q,f'سفارش #{oid} ثبت شد و برای تحویل منتظر بررسی مدیر است.',K([[b('🧾 سفارش‌ها','orders'),b('🏠 منو','home')]])); await admins(ctx,f'👛 سفارش #{oid}\nکاربر: {u.id}\nمحصول: {p["title"]}\nگیرنده: {recipient}\nمبلغ: {money(p["amount"])}',order_buttons(oid))
 elif d=='wallet': await edit(q,f'👛 <b>کیف پول</b>\nموجودی: <b>{money(bal(u.id))}</b>',K([[b('➕ افزایش موجودی','wallet:add')],[b('⬅️ منو','home')]]),ParseMode.HTML)
 elif d=='wallet:add': ctx.user_data['wallet_amount']=True; await edit(q,f'مبلغ افزایش موجودی رو به عدد بفرست (حداقل {money(MIN_TOPUP)}).',K([[b('⬅️ بازگشت','wallet')]]))
 elif d=='orders':
  with con() as c: rs=c.execute('SELECT id,title,amount,status FROM orders WHERE uid=? ORDER BY id DESC LIMIT 10',(u.id,)).fetchall()
  names={'awaiting_receipt':'در انتظار رسید','paid_pending_delivery':'در انتظار تحویل','delivered':'تحویل‌شده','rejected':'ردشده'}; text='🧾 <b>سفارش‌های من</b>\n\n'+('\n\n'.join(f"#{r['id']} · {r['title']} · {money(r['amount'])}\nوضعیت: {names.get(r['status'],r['status'])}" for r in rs) if rs else 'هنوز سفارشی نداری.')
  await edit(q,text,K([[b('⬅️ منو','home')]]),ParseMode.HTML)
 elif d=='feature:gift': await edit(q,setting('text_gift','🎁 این بخش هنوز آماده نشده است. تیم وینکسا در حال تکمیل این قابلیت است؛ لطفاً بعداً دوباره سر بزن.'),K([[b('⬅️ منو','home')]]),ParseMode.HTML)
 elif d=='feature:boost': await edit(q,setting('text_boost','🚀 بخش بوست چنل هنوز آماده نشده است. به‌محض تکمیل، از همین‌جا در دسترس قرار می‌گیرد.'),K([[b('⬅️ منو','home')]]),ParseMode.HTML)
 elif d=='support': await edit(q,setting('text_support_prompt',f'📞 پشتیبانی: @{SUPPORT}'),K([[b('⬅️ منو','home')]]),ParseMode.HTML)
 elif d=='admin':
  if u.id not in ADMINS:return
  with con() as c: n=c.execute("SELECT COUNT(*) n FROM orders WHERE status IN ('awaiting_receipt','paid_pending_delivery')").fetchone()['n']; w=c.execute("SELECT COUNT(*) n FROM wallet WHERE status='pending'").fetchone()['n']
  await edit(q,f'🛠 <b>پنل مدیریت</b>\nسفارش‌های در انتظار: {n}\nدرخواست‌های کیف پول: {w}',K([[b('📋 سفارش‌های در انتظار','adm:orders')],[b('👛 درخواست‌های کیف پول','adm:wallets')],[b('💰 ویرایش قیمت','adm:price')],[b('🌐 تنظیم کانال‌ها و ربات‌ها','adm:links')],[b('🎨 تغییر ایموجی دکمه‌ها','adm:emoji')],[b('📝 ویرایش متن‌ها','adm:texts')],[b('🖌 ادیت رنگ‌ها','adm:colors')],[b('⬅️ منو','home')]]),ParseMode.HTML)
 elif d=='adm:colors':
  if u.id not in ADMINS:return
  ctx.user_data.pop('admin_setting_mode',None)
  page=0; per_page=8
  pages=(len(COLOR_BUTTONS)+per_page-1)//per_page
  rows=[[b(label,'adm:colorpick:'+key)] for key,label in COLOR_BUTTONS[:per_page]]
  rows.append([b('➡️ صفحه بعد','adm:colorpage:1')] if pages>1 else [b('⬅️ پنل مدیریت','admin')])
  if pages>1: rows.append([b('⬅️ پنل مدیریت','admin')])
  await edit(q,f'🖌 <b>ادیت رنگ‌ها</b>\n\nدکمهٔ موردنظرت رو انتخاب کن. هر مورد رنگ جداگانه دارد؛ دکمه‌های تکراری با همان عملکرد هم‌رنگ می‌شوند.\nصفحهٔ ۱ از {pages}',K(rows),ParseMode.HTML)
 elif d.startswith('adm:colorpage:'):
  if u.id not in ADMINS:return
  page=int(d.rsplit(':',1)[1]); per_page=8; pages=(len(COLOR_BUTTONS)+per_page-1)//per_page
  page=max(0,min(page,pages-1)); start=page*per_page
  rows=[[b(label,'adm:colorpick:'+key)] for key,label in COLOR_BUTTONS[start:start+per_page]]
  nav=[]
  if page>0: nav.append(b('⬅️ قبلی',f'adm:colorpage:{page-1}'))
  if page<pages-1: nav.append(b('➡️ بعدی',f'adm:colorpage:{page+1}'))
  if nav: rows.append(nav)
  rows.append([b('⬅️ پنل مدیریت','admin')])
  await edit(q,f'🖌 <b>ادیت رنگ‌ها</b>\n\nصفحهٔ {page+1} از {pages} — دکمه‌ای که می‌خوای تغییر بدی انتخاب کن:',K(rows),ParseMode.HTML)
 elif d.startswith('adm:colorpick:'):
  if u.id not in ADMINS:return
  key=d[len('adm:colorpick:'):]
  item=next((x for x in COLOR_BUTTONS if x[0]==key),None)
  if not item:return
  current=setting('button_color_'+key,'default') or 'default'
  names={'default':'⚪ پیش‌فرض','primary':'🔵 آبی','success':'🟢 سبز','danger':'🔴 قرمز'}
  rows=[[b(names[color],f'adm:colorset:{key}:{color}',None if color=='default' else color)] for color in ('default','primary','success','danger')]
  rows.append([b('⬅️ بازگشت به فهرست','adm:colors')])
  await edit(q,f'🎨 <b>رنگ دکمه: {item[1]}</b>\nرنگ فعلی: {names.get(current,current)}\n\nرنگ جدید رو انتخاب کن:',K(rows),ParseMode.HTML)
 elif d.startswith('adm:colorset:'):
  if u.id not in ADMINS:return
  parts=d.split(':')
  # key names may contain colons; the final segment is always the selected style.
  key=':'.join(parts[2:-1]); color=parts[-1]
  if color not in {'default','primary','success','danger'} or not any(x[0]==key for x in COLOR_BUTTONS):return
  set_setting('button_color_'+key,color)
  item=next(x for x in COLOR_BUTTONS if x[0]==key)
  names={'default':'⚪ پیش‌فرض','primary':'🔵 آبی','success':'🟢 سبز','danger':'🔴 قرمز'}
  await edit(q,f'✅ رنگ «{item[1]}» ذخیره شد: {names[color]}',K([[b('🎨 تغییر رنگ همین دکمه','adm:colorpick:'+key)],[b('🖌 فهرست رنگ‌ها','adm:colors')],[b('⬅️ پنل مدیریت','admin')]]),ParseMode.HTML)
 elif d=='adm:price':
  if u.id not in ADMINS:return
  ctx.user_data.pop('admin_setting_mode',None)
  labels={'premium:3':'پریمیوم ۳ ماهه','premium:6':'پریمیوم ۶ ماهه','premium:12':'پریمیوم ۱۲ ماهه','stars:50':'۵۰ استارز','stars:100':'۱۰۰ استارز','stars:250':'۲۵۰ استارز','stars:500':'۵۰۰ استارز','stars:1000':'۱۰۰۰ استارز'}
  rows=[[b(name,'adm:pricepick:'+key)] for key,name in labels.items()]
  rows.append([b('⬅️ پنل','admin')])
  await edit(q,'💰 <b>تغییر قیمت محصول</b>\n\nمحصول موردنظرت رو انتخاب کن:',K(rows),ParseMode.HTML)
 elif d.startswith('adm:pricepick:'):
  if u.id not in ADMINS:return
  key=d[len('adm:pricepick:'):]
  labels={'premium:3':'پریمیوم ۳ ماهه','premium:6':'پریمیوم ۶ ماهه','premium:12':'پریمیوم ۱۲ ماهه','stars:50':'۵۰ استارز','stars:100':'۱۰۰ استارز','stars:250':'۲۵۰ استارز','stars:500':'۵۰۰ استارز','stars:1000':'۱۰۰۰ استارز'}
  if key not in labels:return
  ctx.user_data['pending_price_key']=key
  ctx.user_data['pending_price_title']=labels[key]
  await edit(q,f'✏️ محصول: <b>{labels[key]}</b>\n\nقیمت فروش جدید رو به تومان وارد کن.\nمثلاً: <code>4000000</code>',K([[b('❌ لغو','adm:pricecancel')],[b('⬅️ پنل','admin')]]),ParseMode.HTML)
 elif d=='adm:pricecancel':
  if u.id not in ADMINS:return
  for k in ('pending_price_key','pending_price_amount','pending_price_title'):ctx.user_data.pop(k,None)
  await edit(q,'تغییر قیمت لغو شد.',K([[b('💰 تغییر قیمت','adm:price')],[b('⬅️ پنل','admin')]]))
 elif d=='adm:priceconfirm':
  if u.id not in ADMINS:return
  key=ctx.user_data.get('pending_price_key'); amount=ctx.user_data.get('pending_price_amount'); title=ctx.user_data.get('pending_price_title','محصول')
  if not key or amount is None:return await edit(q,'اطلاعات قیمت پیدا نشد؛ دوباره شروع کن.',K([[b('💰 تغییر قیمت','adm:price')]]))
  kind,product_key=key.split(':',1)
  setting_key=('PRICE_PREMIUM_'+product_key+'M') if kind=='premium' else ('PRICE_STARS_'+product_key)
  set_setting(setting_key,str(amount))
  live_rate=await ton_rate()
  if live_rate:set_setting(f'ton_ref_{kind}_{product_key}',str(live_rate))
  if kind=='premium': PREM[product_key]=amount
  else: STARS[product_key]=amount
  for k in ('pending_price_key','pending_price_amount','pending_price_title'):ctx.user_data.pop(k,None)
  await edit(q,f'✅ قیمت ذخیره شد.\n\nمحصول: {title}\nقیمت جدید: <b>{money(amount)}</b>',K([[b('💰 تغییر محصول دیگر','adm:price')],[b('⬅️ پنل مدیریت','admin')]]),ParseMode.HTML)
 elif d=='adm:links':
  if u.id not in ADMINS:return
  ctx.user_data['admin_setting_mode']='links'; await edit(q,'برای تغییر هر لینک، یک خط با قالب زیر بفرست (چهار لینک قابل تنظیم است):\n1|عنوان|https://t.me/example\n2|عنوان|https://t.me/example\n3|عنوان|https://t.me/example\n4|عنوان|https://t.me/example',K([[b('⬅️ پنل','admin')]]))
 elif d=='adm:texts':
  if u.id not in ADMINS:return
  text_items=[('menu_prompt','🏠 متن منوی اصلی'),('welcome','👋 پیام شروع'),('help','📘 راهنما'),('support_prompt','📞 متن پشتیبانی'),('trust','🔐 متن اعتمادسازی'),('gift','🎁 متن گیفت'),('boost','🚀 متن بوست')]
  await edit(q,'📝 <b>ویرایش متن‌ها</b>\nیکی از متن‌ها رو انتخاب کن. ایموجی پریمیوم هم داخل متن پشتیبانی می‌شه.',K([[b(label,'adm:textedit:'+key)] for key,label in text_items]+[[b('⬅️ بازگشت','admin')]]),ParseMode.HTML)
 elif d.startswith('adm:textedit:'):
  if u.id not in ADMINS:return
  key=d.split(':',2)[2]
  labels={'menu_prompt':'متن منوی اصلی','welcome':'پیام شروع','help':'راهنما','support_prompt':'متن پشتیبانی','trust':'متن اعتمادسازی','gift':'متن گیفت','boost':'متن بوست'}
  if key not in labels:return
  ctx.user_data['admin_setting_mode']='text_edit_'+key;ctx.user_data['admin_text_key']=key
  await edit(q,f'✏️ <b>{labels[key]}</b>\nمتن جدید رو در یک پیام بفرست. ایموجی‌های پریمیوم/Custom Emoji هم ذخیره می‌شن.',K([[b('❌ لغو','adm:textcancel')],[b('⬅️ فهرست متن‌ها','adm:texts')]]),ParseMode.HTML)
 elif d=='adm:textcancel':
  if u.id not in ADMINS:return
  ctx.user_data.pop('admin_setting_mode',None);ctx.user_data.pop('admin_text_key',None)
  await edit(q,'ویرایش متن لغو شد.',K([[b('📝 ویرایش متن‌ها','adm:texts')],[b('⬅️ پنل','admin')]]))
 elif d=='adm:emoji':
  if u.id not in ADMINS:return
  emoji_items=[('stars','⭐ استارز'),('premium','💎 پریمیوم'),('wallet','👛 کیف پول'),('orders','🧾 سفارش‌ها'),('links','🌐 لینک‌ها'),('support','📞 پشتیبانی'),('admin','🛠 مدیریت')]
  await edit(q,'🎨 <b>انتخاب ایموجی دکمه‌ها</b>\nاول مورد رو انتخاب کن؛ بعد ایموجی معمولی یا پریمیوم رو در یک پیام بفرست. شناسهٔ ایموجی پریمیوم ذخیره می‌شه.',K([[b(label,'adm:emojipick:'+key)] for key,label in emoji_items]+[[b('⬅️ پنل','admin')]]),ParseMode.HTML)
 elif d.startswith('adm:emojipick:'):
  if u.id not in ADMINS:return
  key=d.split(':',2)[2]
  if key not in {'stars','premium','wallet','orders','links','support','admin'}:return
  ctx.user_data['admin_setting_mode']='emoji_pick';ctx.user_data['emoji_pick_key']=key
  await edit(q,f'🎨 ایموجی جدید برای «{key}» رو همین‌جا بفرست؛ ایموجی پریمیوم هم قبوله.',K([[b('❌ لغو','adm:emojicancel')],[b('⬅️ فهرست ایموجی‌ها','adm:emoji')]]))
 elif d=='adm:emojicancel':
  if u.id not in ADMINS:return
  ctx.user_data.pop('admin_setting_mode',None);ctx.user_data.pop('emoji_pick_key',None)
  await edit(q,'تغییر ایموجی لغو شد.',K([[b('🎨 ایموجی‌ها','adm:emoji')],[b('⬅️ پنل','admin')]]))
 elif d=='adm:orders':
  if u.id not in ADMINS:return
  with con() as c: rs=c.execute("SELECT id,uid,title,amount,status FROM orders WHERE status IN ('awaiting_receipt','paid_pending_delivery') ORDER BY id DESC LIMIT 20").fetchall()
  await edit(q,'📋 سفارش‌های در انتظار\n\n'+('\n'.join(f"#{r['id']} · کاربر {r['uid']} · {r['title']} · {money(r['amount'])}" for r in rs) if rs else 'موردی نیست.'),K([[b(f"باز کردن #{r['id']}",f"adm:order:{r['id']}")] for r in rs]+[[b('⬅️ پنل','admin')]]))
 elif d.startswith('adm:order:'):
  if u.id not in ADMINS:return
  oid=int(d.rsplit(':',1)[1])
  with con() as c: r=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
  if r: await edit(q,f"سفارش #{oid}\nکاربر: {r['uid']}\nمحصول: {r['title']}\nگیرنده: {r['recipient']}\nمبلغ: {money(r['amount'])}\nوضعیت: {r['status']}",order_buttons(oid))
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
 if m.text and ctx.user_data.get('await_custom_stars'):
  raw=m.text.replace(',','').replace('٬','').replace('،','').strip()
  if not raw.isdigit() or not (50 <= int(raw) <= 100000):
   await m.reply_text('تعداد معتبر وارد کن؛ حداقل 50 و حداکثر 100000 است.')
   return
  count=int(raw); ctx.user_data['await_custom_stars']=False
  unit=await current_price('stars','1000')/1000
  amount=max(1,round(unit*count))
  ctx.user_data['product']={'kind':'stars','key':'custom_'+str(count),'title':f'{count:,} استارز دلخواه','amount':amount}
  await m.reply_text(f'✨ تعداد انتخاب‌شده: {count:,} استارز\n💰 مبلغ: {money(amount)}\n\nبرای ادامه گیرنده رو انتخاب کن:',reply_markup=K([[b('🙋 برای خودم','recipient:self','success')],[b('🎁 برای شخص دیگر','recipient:other','primary')],[b('⬅️ بازگشت','buy:stars')]]))
  return
 if m.text and ctx.user_data.get('await_recipient'):
  rec=m.text.strip(); ctx.user_data['await_recipient']=False
  if not (rec.startswith('@') and len(rec)>1 or rec.isdigit()): ctx.user_data['await_recipient']=True; await m.reply_text('فرمت آیدی درست نیست. @username یا آیدی عددی بفرست.'); return
  ctx.user_data['recipient']=rec; p=ctx.user_data.get('product')
  if not p: await m.reply_text('سفارش پیدا نشد؛ /start رو بزن.'); return
  await m.reply_text(f'🔎 گیرنده: {rec}\n\nربات نمی‌تونه اطلاعات خصوصی یا جزئیات کامل حساب کاربر رو از روی آیدی واکشی کنه. بررسی کن آیدی درست باشه و تأیید رو بزن.',reply_markup=K([[b('✅ تأیید گیرنده','recipient:confirm')],[b('✏️ وارد کردن دوباره','recipient:other')],[b('❌ لغو','home')]])); return
 if m.text and ctx.user_data.get('pending_price_key') and u.id in ADMINS:
  raw=m.text.replace(',','').replace('٬','').replace('،','').strip()
  if not raw.isdigit() or int(raw)<=0:
   await m.reply_text('❌ قیمت معتبر نیست. فقط عدد مثبت به تومان بفرست؛ مثلاً 4000000.')
   return
  amount=int(raw)
  ctx.user_data['pending_price_amount']=amount
  title=ctx.user_data.get('pending_price_title','محصول')
  await m.reply_text(f'🔎 <b>تأیید قیمت جدید</b>\n\nمحصول: {title}\nقیمت جدید: <b>{money(amount)}</b>\n\nذخیره بشه؟',reply_markup=K([[b('✅ تأیید و ذخیره','adm:priceconfirm','success')],[b('✏️ وارد کردن دوباره','adm:pricepick:'+ctx.user_data['pending_price_key'])],[b('❌ لغو','adm:pricecancel','danger')]]),parse_mode=ParseMode.HTML)
  return
 if m.text and ctx.user_data.get('admin_setting_mode','').startswith('text_edit_') and u.id in ADMINS:
  mode=ctx.user_data.pop('admin_setting_mode')
  key=ctx.user_data.pop('admin_text_key',mode[len('text_edit_'):])
  setting_keys={'menu_prompt':'text_menu_prompt','welcome':'text_welcome','help':'text_help','support_prompt':'text_support_prompt','trust':'text_trust','gift':'text_gift','boost':'text_boost'}
  rich_text=(m.text_html or m.text).strip()
  if key in setting_keys:
   set_setting(setting_keys[key],rich_text[:8000])
   await m.reply_text('✅ متن ذخیره شد؛ ایموجی‌های پریمیوم هم همراه متن ذخیره شدن.',reply_markup=K([[b('📝 ویرایش متن‌ها','adm:texts')],[b('⬅️ پنل مدیریت','admin')]]))
  else: await m.reply_text('کلید متن معتبر نیست.')
  return
 if m.text and ctx.user_data.get('admin_setting_mode')=='emoji_pick' and u.id in ADMINS:
  key=ctx.user_data.pop('emoji_pick_key',None);ctx.user_data.pop('admin_setting_mode',None)
  if not key or key not in {'stars','premium','wallet','orders','links','support','admin'}:
   await m.reply_text('مورد ایموجی پیدا نشد؛ دوباره از منو انتخاب کن.',reply_markup=K([[b('🎨 ایموجی‌ها','adm:emoji')]]));return
  entity=next((e for e in (m.entities or []) if e.type=='custom_emoji'),None)
  if entity:
   fallback=m.text[entity.offset:entity.offset+entity.length]
   value=f'<tg-emoji emoji-id="{entity.custom_emoji_id}">{fallback}</tg-emoji>'
  else: value=m.text.strip()
  if not value or len(value)>64:
   await m.reply_text('فقط یک ایموجی بفرست.',reply_markup=K([[b('🎨 دوباره انتخاب کن','adm:emoji')]]));return
  set_setting('emoji_'+key,value)
  await m.reply_text('✅ ایموجی ذخیره شد. شناسهٔ ایموجی پریمیوم هم حفظ شد.',reply_markup=K([[b('🎨 انتخاب ایموجی دیگر','adm:emoji')],[b('⬅️ پنل مدیریت','admin')]]),parse_mode=ParseMode.HTML)
  return
 if m.text and ctx.user_data.get('admin_setting_mode') and u.id in ADMINS:
  mode=ctx.user_data.pop('admin_setting_mode'); lines=m.text.splitlines(); ok=0
  try:
   if mode=='price':
    for line in lines:
     if '=' not in line: continue
     key,val=line.split('=',1); key=key.strip(); val=val.strip()
     if key in {'PRICE_PREMIUM_3M','PRICE_PREMIUM_6M','PRICE_PREMIUM_12M','PRICE_STARS_50','PRICE_STARS_100','PRICE_STARS_250','PRICE_STARS_500','PRICE_STARS_1000'} and val.isdigit(): set_setting(key,val); ok+=1
    # values persist in DB and update active dictionaries
    for k in ('3','6','12'): PREM[k]=int(setting('PRICE_PREMIUM_'+k+'M',str(PREM[k])))
    for k in ('50','100','250','500','1000'): STARS[k]=int(setting('PRICE_STARS_'+k,str(STARS[k])))
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
async def auto_react(up,ctx):
 m=up.effective_message; chat=up.effective_chat
 if not m or not chat or chat.type!="private" or (up.effective_user and up.effective_user.is_bot): return
 # Telegram bots are limited to one reaction per message; choose from standard emoji.
 choices=["❤️","🔥","🥰","🎉","👏","😍","💯","🤩","😁","😊","🙏","💖","💕","🤗","💪","⭐","🌟","✨","👌","🫶","🤣","👍","🥳"]
 chosen=random.choice(choices)
 try:
  await ctx.bot.set_message_reaction(chat_id=chat.id,message_id=m.message_id,reaction=[ReactionTypeEmoji(emoji=chosen)],is_big=False)
  logging.info("Auto-reaction set: chat=%s message=%s emoji=%s",chat.id,m.message_id,chosen)
 except Exception as e:
  logging.warning("Auto-reaction failed: chat=%s message=%s emoji=%s error=%s",chat.id,m.message_id,chosen,str(e)[:300])

async def post_init(app):
 init()
 for k in ('3','6','12'): PREM[k]=int(setting('PRICE_PREMIUM_'+k+'M',str(PREM[k])))
 for k in ('50','100','250','500','1000'): STARS[k]=int(setting('PRICE_STARS_'+k,str(STARS[k])))
 try: await app.bot.set_my_commands([('start','شروع ربات'),('help','راهنما')])
 except TelegramError: pass
 logging.info('Vynexa Stars started')
def main():
 if not TOKEN:raise SystemExit('BOT_TOKEN را در Environment Variables هاست تنظیم کن.')
 app=Application.builder().token(TOKEN).post_init(post_init).concurrent_updates(32).connection_pool_size(64).pool_timeout(5).build();app.add_handler(CommandHandler('start',start));app.add_handler(CommandHandler('help',help_command));app.add_handler(CallbackQueryHandler(cb));app.add_handler(MessageHandler(filters.PHOTO|(filters.TEXT&~filters.COMMAND),messages));app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.ALL,auto_react),group=1);app.run_polling(allowed_updates=Update.ALL_TYPES)
if __name__=='__main__':main()
