# track/db.py
# Hyperliquid Telegram 互動式監控跟單系統 - 資料庫操作模組（管理員可管理全系統地址）

import sqlite3
from datetime import datetime

DB_PATH = "trades.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # 用戶表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT UNIQUE,
            username TEXT,
            okx_uid TEXT,
            contributor_name TEXT,
            verified BOOLEAN DEFAULT 0
        )
    ''')

    # 用戶地址監控表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            address TEXT,
            monitor BOOLEAN DEFAULT 1,
            monitor_ratio REAL DEFAULT 1.0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # 地址績效表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS address_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT UNIQUE,
            last_30d_pnl REAL DEFAULT 0,
            last_30d_win_rate REAL DEFAULT 0,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 全系統監控地址表（最多 10 筆由管理員控制）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT UNIQUE,
            monitor_ratio REAL DEFAULT 1.0
        )
    ''')

    conn.commit()
    conn.close()

# ---------- 使用者相關 ----------
def add_user(telegram_id, username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)', (telegram_id, username))
    conn.commit()
    conn.close()

def verify_user(telegram_id, okx_uid=None, contributor_name=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users
        SET verified = 1,
            okx_uid = COALESCE(?, okx_uid),
            contributor_name = COALESCE(?, contributor_name)
        WHERE telegram_id = ?
    ''', (okx_uid, contributor_name, telegram_id))
    conn.commit()
    conn.close()

# ---------- 個別用戶地址監控 ----------
def add_user_address(telegram_id, address, monitor_ratio=1.0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    if user:
        user_id = user['id']
        cursor.execute('INSERT INTO user_addresses (user_id, address, monitor_ratio) VALUES (?, ?, ?)',
                       (user_id, address, monitor_ratio))
        conn.commit()
    conn.close()

def get_user_addresses(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ua.address, ua.monitor_ratio, ua.monitor
        FROM user_addresses ua
        JOIN users u ON ua.user_id = u.id
        WHERE u.telegram_id = ?
    ''', (telegram_id,))
    results = cursor.fetchall()
    conn.close()
    return results

def update_monitor_ratio(telegram_id, address, new_ratio):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE user_addresses
        SET monitor_ratio = ?
        WHERE address = ? AND user_id = (SELECT id FROM users WHERE telegram_id = ?)
    ''', (new_ratio, address, telegram_id))
    conn.commit()
    conn.close()

# ---------- 全系統監控地址（管理員使用） ----------
def add_system_address(address, monitor_ratio=1.0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as cnt FROM system_addresses')
    count = cursor.fetchone()['cnt']
    if count >= 10:
        conn.close()
        raise Exception("已達到最大可監控地址數量上限（10）")
    cursor.execute('INSERT OR IGNORE INTO system_addresses (address, monitor_ratio) VALUES (?, ?)',
                   (address, monitor_ratio))
    conn.commit()
    conn.close()

def update_system_monitor_ratio(address, new_ratio):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE system_addresses SET monitor_ratio = ? WHERE address = ?', (new_ratio, address))
    conn.commit()
    conn.close()

def get_all_monitored_addresses():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT address, monitor_ratio FROM system_addresses')
    results = cursor.fetchall()
    conn.close()
    return results

# ---------- 地址績效查詢 ----------
def get_address_performance(address):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT last_30d_pnl, last_30d_win_rate
        FROM address_performance
        WHERE address = ?
    ''', (address,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result['last_30d_pnl'], result['last_30d_win_rate']
    else:
        return 0.0, 0.0

# ---------- 初始化執行 ----------
if __name__ == "__main__":
    init_db()
    print("✅ 資料庫初始化完成，表格已建立")
