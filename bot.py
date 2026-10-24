import os, sqlite3, logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton as B, InlineKeyboardMarkup as K
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN=os.getenv('BOT_TOKEN','').strip()
ADMINS={int(x) for x in os.getenv('ADMIN_IDS','').split(',') if x.strip().isdigit()}
DB=os.getenv('DB_PATH','vynexa_stars.sqlite3'); CARD=os.getenv('CARD_NUMBER','شماره کارت را در تنظیمات وارد کنید'); HOLDER=os.getenv('CARD_HOLDER','نام صاحب کارت را در تنظیمات وارد کنید'); SUPPORT=os.getenv('SUPPORT_USERNAME','fbugtjng').lstrip('@'); CUR=os.getenv('CURRENCY','تومان'); MIN_TOPUP=int(os.getenv('MIN_WALLET_TOPUP','10000')); EMOJI=os.getenv('CUSTOM_EMOJI','').strip()
PREM={k:int(os.getenv('PRICE_PREMIUM_'+k+'M','0')) for k in ('3','6','12')}; STARS={k:int(os.getenv('PRICE_STARS_'+k,'0')) for k in ('50','100','250','500','1000')}
logging.basicConfig(level=logging.INFO)
def now(): return datetime.now(timezone.utc).isoformat()
def money(n): return f'{int(n):,} {CUR}'
def con():
 c=sqlite3.connect(DB,timeout=20); c.row_factory=sqlite3.Row; return c
def init():
 with con() as c: c.executescript('''CREATE TABLE IF NOT EXISTS users(uid INTEGER PRIMARY KEY,username TEXT,first_name TEXT,balance INTEGER DEFAULT 0,created TEXT); CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,uid INTEGER,kind TEXT,pkey TEXT,title TEXT,amount INTEGER,method TEXT,status TEXT,receipt TEXT,created TEXT); CREATE TABLE IF NOT EXISTS wallet(id INTEGER PRIMARY KEY AUTOINCREMENT,uid INTEGER,amount INTEGER,status TEXT,receipt TEXT,created TEXT);''')
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
 rows=[[b('⭐ خرید استارز','buy:stars','success'),b('💎 خرید پریمیوم','buy:premium','primary')],[b('👛 کیف پول','wallet'),b('🧾 سفارش‌های من','orders')],[b('📞 پشتیبانی','support')]]
 if uid in ADMINS: rows.append([b('🛠 پنل مدیریت','admin','danger')])
 return K(rows)
def product_menu(kind):
 data=PREM if kind=='premium' else STARS; labels={'3':'پریمیوم ۳ ماهه','6':'پریمیوم ۶ ماهه','12':'پریمیوم ۱۲ ماهه'}
 return K([[b(f"{labels.get(k,k+' استارز')} — {money(v) if v>0 else 'قیمت تنظیم نشده'}",f'product:{kind}:{k}')] for k,v in data.items()]+[[b('⬅️ بازگشت','home')]])
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
async def cb(up,ctx):
 q=up.callback_query; await q.answer(); u=up.effective_user; ensure(u); d=q.data
 if d=='home': ctx.user_data.pop('product',None); await edit(q,'✨ <b>Vynexa Stars</b>\nچه کاری برات انجام بدم؟',menu(u.id),ParseMode.HTML)
 elif d.startswith('buy:'): await edit(q,'بسته موردنظرت رو انتخاب کن:',product_menu(d.split(':')[1]))
 elif d.startswith('product:'):
  _,kind,key=d.split(':'); price=(PREM if kind=='premium' else STARS)[key]
  if price<=0: await q.answer('قیمت این محصول هنوز تنظیم نشده.',show_alert=True); return
  title=({'3':'پریمیوم ۳ ماهه','6':'پریمیوم ۶ ماهه','12':'پریمیوم ۱۲ ماهه'}[key] if kind=='premium' else key+' استارز'); ctx.user_data['product']={'kind':kind,'key':key,'title':title,'amount':price}
  await edit(q,f'🧾 <b>پیش‌فاکتور</b>\nمحصول: {title}\nمبلغ: <b>{money(price)}</b>\n\nروش پرداخت رو انتخاب کن:',K([[b('💳 کارت‌به‌کارت','pay:card','primary')],[b('👛 کیف پول','pay:wallet','success')],[b('⬅️ بازگشت','buy:'+kind)]]),ParseMode.HTML)
 elif d.startswith('pay:'):
  p=ctx.user_data.get('product')
  if not p: await edit(q,'از منو دوباره محصول رو انتخاب کن.',menu(u.id)); return
  method=d.split(':')[1]
  if method=='wallet' and bal(u.id)<p['amount']: await edit(q,f'موجودی کافی نیست.\nموجودی: {money(bal(u.id))}\nمبلغ سفارش: {money(p["amount"])}',K([[b('➕ افزایش موجودی','wallet:add')],[b('⬅️ منو','home')]])); return
  with con() as c:
   oid=c.execute('INSERT INTO orders(uid,kind,pkey,title,amount,method,status,created) VALUES(?,?,?,?,?,?,?,?)',(u.id,p['kind'],p['key'],p['title'],p['amount'],method,'awaiting_receipt' if method=='card' else 'paid_pending_delivery',now())).lastrowid
   if method=='wallet' and not c.execute('UPDATE users SET balance=balance-? WHERE uid=? AND balance>=?',(p['amount'],u.id,p['amount'])).rowcount: c.execute('DELETE FROM orders WHERE id=?',(oid,)); await edit(q,'موجودی کافی نیست.',menu(u.id)); return
  ctx.user_data.pop('product',None)
  if method=='card':
   ctx.user_data['receipt_order']=oid; await edit(q,f'💳 <b>سفارش #{oid}</b>\nمحصول: {p["title"]}\nمبلغ: <b>{money(p["amount"])}</b>\n\nصاحب کارت: <b>{HOLDER}</b>\nشماره کارت: <code>{CARD}</code>\n\nبعد از واریز، عکس رسید رو همین‌جا بفرست.',K([[b('🏠 منو','home')]]),ParseMode.HTML)
  else: await edit(q,f'سفارش #{oid} ثبت شد و برای تحویل منتظر بررسی مدیر است.',K([[b('🧾 سفارش‌ها','orders'),b('🏠 منو','home')]])); await admins(ctx,f'👛 سفارش #{oid}\nکاربر: {u.id}\nمحصول: {p["title"]}\nمبلغ: {money(p["amount"])}',order_buttons(oid))
 elif d=='wallet': await edit(q,f'👛 <b>کیف پول</b>\nموجودی: <b>{money(bal(u.id))}</b>',K([[b('➕ افزایش موجودی','wallet:add')],[b('⬅️ منو','home')]]),ParseMode.HTML)
 elif d=='wallet:add': ctx.user_data['wallet_amount']=True; await edit(q,f'مبلغ افزایش موجودی رو به عدد بفرست (حداقل {money(MIN_TOPUP)}).',K([[b('⬅️ بازگشت','wallet')]]))
 elif d=='orders':
  with con() as c: rs=c.execute('SELECT id,title,amount,status FROM orders WHERE uid=? ORDER BY id DESC LIMIT 10',(u.id,)).fetchall()
  names={'awaiting_receipt':'در انتظار رسید','paid_pending_delivery':'در انتظار تحویل','delivered':'تحویل‌شده','rejected':'ردشده'}; text='🧾 <b>سفارش‌های من</b>\n\n'+('\n\n'.join(f"#{r['id']} · {r['title']} · {money(r['amount'])}\nوضعیت: {names.get(r['status'],r['status'])}" for r in rs) if rs else 'هنوز سفارشی نداری.')
  await edit(q,text,K([[b('⬅️ منو','home')]]),ParseMode.HTML)
 elif d=='support': await edit(q,f'📞 پشتیبانی: @{SUPPORT}',K([[b('⬅️ منو','home')]]))
 elif d=='admin':
  if u.id not in ADMINS:return
  with con() as c: n=c.execute("SELECT COUNT(*) n FROM orders WHERE status IN ('awaiting_receipt','paid_pending_delivery')").fetchone()['n']; w=c.execute("SELECT COUNT(*) n FROM wallet WHERE status='pending'").fetchone()['n']
  await edit(q,f'🛠 <b>پنل مدیریت</b>\nسفارش‌های در انتظار: {n}\nدرخواست‌های کیف پول: {w}',K([[b('📋 سفارش‌های در انتظار','adm:orders')],[b('👛 درخواست‌های کیف پول','adm:wallets')],[b('⬅️ منو','home')]]),ParseMode.HTML)
 elif d=='adm:orders':
  if u.id not in ADMINS:return
  with con() as c: rs=c.execute("SELECT id,uid,title,amount,status FROM orders WHERE status IN ('awaiting_receipt','paid_pending_delivery') ORDER BY id DESC LIMIT 20").fetchall()
  await edit(q,'📋 سفارش‌های در انتظار\n\n'+('\n'.join(f"#{r['id']} · کاربر {r['uid']} · {r['title']} · {money(r['amount'])}" for r in rs) if rs else 'موردی نیست.'),K([[b(f"باز کردن #{r['id']}",f"adm:order:{r['id']}")] for r in rs]+[[b('⬅️ پنل','admin')]]))
 elif d.startswith('adm:order:'):
  if u.id not in ADMINS:return
  oid=int(d.rsplit(':',1)[1])
  with con() as c: r=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
  if r: await edit(q,f"سفارش #{oid}\nکاربر: {r['uid']}\nمحصول: {r['title']}\nمبلغ: {money(r['amount'])}\nوضعیت: {r['status']}",order_buttons(oid))
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
    await admins(ctx,f"💳 رسید سفارش #{oid}\nکاربر: {u.id}\nمحصول: {r['title']}\nمبلغ: {money(r['amount'])}",order_buttons(oid))
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
async def post_init(app):init();logging.info('Vynexa Stars started')
def main():
 if not TOKEN:raise SystemExit('BOT_TOKEN را در Environment Variables هاست تنظیم کن.')
 app=Application.builder().token(TOKEN).post_init(post_init).build();app.add_handler(CommandHandler('start',start));app.add_handler(CommandHandler('help',start));app.add_handler(CallbackQueryHandler(cb));app.add_handler(MessageHandler(filters.PHOTO|(filters.TEXT&~filters.COMMAND),messages));app.run_polling(allowed_updates=Update.ALL_TYPES)
if __name__=='__main__':main()
