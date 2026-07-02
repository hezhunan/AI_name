import sqlite3

DB_PATH = "db.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# 根据登录账号（手机号）查询用户
def get_user_by_account(account):
    conn = get_conn()
    row = conn.execute("SELECT * FROM user WHERE account = ?", (account,)).fetchone()
    conn.close()
    return dict(row) if row else None

# 注册用户：账号(手机号)、用户名、密码
def add_user(account, username, password):
    conn = get_conn()
    try:
        conn.execute("INSERT INTO user(account, username, password) VALUES (?, ?, ?)", (account, username, password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # 账号重复
        return False
    finally:
        conn.close()

# ========== 起名搜索记录 ==========
def add_search_record(user_id, surname, gender, birth):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO search_record(user_id, surname, gender, birth, create_time)
        VALUES (?, ?, ?, ?, datetime('now','localtime'))
    """, (user_id, surname, gender, birth))
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid

def get_user_search(user_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM search_record WHERE user_id = ? ORDER BY create_time DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ========== 名字收藏 ==========
def add_collect(user_id, name, meaning, five_attr, record_id):
    conn = get_conn()
    conn.execute("""
        INSERT INTO collect_name(user_id, full_name, meaning, five_attr, record_id)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, name, meaning, five_attr, record_id))
    conn.commit()
    conn.close()

def del_collect(user_id, collect_id):
    conn = get_conn()
    conn.execute("DELETE FROM collect_name WHERE id = ? AND user_id = ?", (collect_id, user_id))
    conn.commit()
    conn.close()

def get_user_collect(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM collect_name WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ========== 五行、诗词素材（大模型兜底） ==========
def get_five_words(target_five):
    conn = get_conn()
    res = conn.execute("SELECT word FROM word_lib WHERE five = ?", (target_five,)).fetchall()
    conn.close()
    return [r[0] for r in res]

def get_all_poems():
    conn = get_conn()
    res = conn.execute("SELECT content FROM poem").fetchall()
    conn.close()
    return [r[0] for r in res]