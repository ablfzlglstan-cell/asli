# database.py
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

DB_NAME = "fox_reporter.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    # جدول کاربران
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        role TEXT DEFAULT 'user',
        subscription_until TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        is_blocked INTEGER DEFAULT 0
    )""")

    # جدول سشن‌ها (اکانت‌های تلگرام)
    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone_number TEXT UNIQUE,
        api_id INTEGER,
        api_hash TEXT,
        session_string TEXT,
        status TEXT DEFAULT 'active',
        assigned_to_admin_id INTEGER,
        last_used TEXT,
        FOREIGN KEY(assigned_to_admin_id) REFERENCES users(user_id)
    )""")

    # جدول سرورهای ایمیل (SMTP)
    c.execute("""CREATE TABLE IF NOT EXISTS smtp_servers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        password TEXT,
        host TEXT DEFAULT 'smtp.gmail.com',
        port INTEGER DEFAULT 587,
        is_active INTEGER DEFAULT 1,
        is_tested INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    # جدول لاگ ریپورت‌ها
    c.execute("""CREATE TABLE IF NOT EXISTS reports_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_type TEXT,
        target_id TEXT,
        reporter_user_id INTEGER,
        status TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        details TEXT
    )""")

    # جدول تنظیمات عمومی
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")

    # تنظیمات پیش‌فرض
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('mandatory_channel_id', '')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('report_delay_min', '1')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('report_delay_max', '3')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_limit', '5')")

    conn.commit()
    conn.close()

def add_user(user_id: int, username: str = None, role: str = 'user'):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO users (user_id, username, role) VALUES (?, ?, ?)", 
                 (user_id, username, role))
    conn.commit()
    conn.close()

def update_role(user_id: int, role: str):
    conn = get_db()
    conn.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))
    conn.commit()
    conn.close()

def set_subscription(user_id: int, until_date: str):
    conn = get_db()
    conn.execute("UPDATE users SET subscription_until = ? WHERE user_id = ?", (until_date, user_id))
    conn.commit()
    conn.close()

def get_user(user_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_all_users(role: str = None) -> List[dict]:
    conn = get_db()
    if role:
        rows = conn.execute("SELECT * FROM users WHERE role = ?", (role,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_smtp(email: str, password: str):
    conn = get_db()
    conn.execute("INSERT INTO smtp_servers (email, password) VALUES (?, ?)", (email, password))
    conn.commit()
    conn.close()

def get_smtp_servers(is_active_only: bool = False) -> List[dict]:
    conn = get_db()
    if is_active_only:
        rows = conn.execute("SELECT * FROM smtp_servers WHERE is_active = 1").fetchall()
    else:
        rows = conn.execute("SELECT * FROM smtp_servers").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def toggle_smtp(smtp_id: int, is_active: bool):
    conn = get_db()
    conn.execute("UPDATE smtp_servers SET is_active = ? WHERE id = ?", (int(is_active), smtp_id))
    conn.commit()
    conn.close()

def mark_smtp_tested(smtp_id: int):
    conn = get_db()
    conn.execute("UPDATE smtp_servers SET is_tested = 1 WHERE id = ?", (smtp_id,))
    conn.commit()
    conn.close()

def add_session(phone: str, api_id: int, api_hash: str, session_string: str, admin_id: int = None):
    conn = get_db()
    conn.execute("INSERT INTO sessions (phone_number, api_id, api_hash, session_string, assigned_to_admin_id) VALUES (?, ?, ?, ?, ?)",
                 (phone, api_id, api_hash, session_string, admin_id))
    conn.commit()
    conn.close()

def get_sessions(admin_id: int = None, all_admins: bool = False) -> List[dict]:
    conn = get_db()
    if all_admins:
        rows = conn.execute("SELECT * FROM sessions").fetchall()
    elif admin_id:
        rows = conn.execute("SELECT * FROM sessions WHERE assigned_to_admin_id = ? OR assigned_to_admin_id IS NULL", (admin_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM sessions WHERE assigned_to_admin_id IS NULL").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def assign_session(session_id: int, admin_id: int):
    conn = get_db()
    conn.execute("UPDATE sessions SET assigned_to_admin_id = ? WHERE id = ?", (admin_id, session_id))
    conn.commit()
    conn.close()

def release_session(session_id: int):
    conn = get_db()
    conn.execute("UPDATE sessions SET assigned_to_admin_id = NULL WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

def log_report(target_type: str, target_id: str, reporter_id: int, status: str, details: str = ""):
    conn = get_db()
    conn.execute("INSERT INTO reports_log (target_type, target_id, reporter_user_id, status, details) VALUES (?, ?, ?, ?, ?)",
                 (target_type, target_id, reporter_id, status, details))
    conn.commit()
    conn.close()

def get_reports_stats(user_id: int = None) -> dict:
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

def get_settings() -> dict:
    conn = get_db()
    rows = conn.execute("SELECT * FROM settings").fetchall()
    conn.close()
    return {r['key']: r['value'] for r in rows}

def update_setting(key: str, value: str):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def create_ticket(user_id: int, message: str):
    conn = get_db()
    conn.execute("INSERT INTO tickets (user_id, message, created_at, status) VALUES (?, ?, ?, 'open')",
                 (user_id, message, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_tickets(status: str = None) -> List[dict]:
    conn = get_db()
    if status:
        rows = conn.execute("SELECT * FROM tickets WHERE status = ?", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM tickets ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def close_ticket(ticket_id: int):
    conn = get_db()
    conn.execute("UPDATE tickets SET status = 'closed', closed_at = ? WHERE id = ?", 
                 (datetime.now().isoformat(), ticket_id))
    conn.commit()
    conn.close()

def reply_to_ticket(ticket_id: int, message: str):
    conn = get_db()
    conn.execute("INSERT INTO ticket_replies (ticket_id, message, sender_id, created_at) VALUES (?, ?, ?, ?)",
                 (ticket_id, message, 0, datetime.now().isoformat())) # sender_id=0 means bot
    conn.commit()
    conn.close()

def get_ticket_history(ticket_id: int) -> List[dict]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM ticket_replies WHERE ticket_id = ? ORDER BY created_at ASC", (ticket_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def block_user(user_id: int):
    conn = get_db()
    conn.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def unblock_user(user_id: int):
    conn = get_db()
    conn.execute("UPDATE users SET is_blocked = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()