import sys
import os
sys.stdout.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"
import sqlite3
import json

DB_PATH = "db.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ==================== 用户模块 ====================
def get_user_by_account(account):
    conn = get_conn()
    row = conn.execute("SELECT * FROM user WHERE account = ?", (account,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(uid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM user WHERE id = ?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def add_user(account, username, password):
    conn = get_conn()
    try:
        conn.execute("INSERT INTO user(account, username, password) VALUES (?, ?, ?)", (account, username, password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# ==================== 起名记录完整存储（主表+名字子表，事务） ====================
def add_full_search_record(user_id, input_data, pillar, analysis):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO search_record (
                user_id, surname, gender, birth,
                pillar_year, pillar_month, pillar_day, pillar_hour,
                zodiac, time_period, birth_element, balance, full_analysis
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            user_id,
            input_data["surname"],
            input_data["gender"],
            input_data["birth"],
            pillar["year"],
            pillar["month"],
            pillar["day"],
            pillar["hour"],
            pillar["zodiac"],
            pillar["time_period"],
            analysis["birth_element"],
            analysis["balance"],
            json.dumps(analysis["full_analysis"], ensure_ascii=False, default=str)
        ))
        record_id = cur.lastrowid
        # 插入3个推荐名
        for item in analysis["suggestions"]:
            cur.execute("""
                INSERT INTO search_name_item (record_id, name, meaning, source_tags)
                VALUES (?,?,?,?)
            """, (
                record_id,
                item["name"],
                item["meaning"],
                json.dumps(item["source_tags"], ensure_ascii=False, default=str)
            ))
        conn.commit()
        print(f"DB写入成功 记录{record_id}")
        return record_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# 获取用户简易浏览列表
def get_user_search_list(user_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, surname, gender, birth, create_time
        FROM search_record
        WHERE user_id = ?
        ORDER BY create_time DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# 根据ID获取完整八字+所有名字
def get_full_search_by_record_id(record_id, user_id):
    conn = get_conn()
    main_row = conn.execute("""
        SELECT * FROM search_record WHERE id = ? AND user_id = ?
    """, (record_id, user_id)).fetchone()
    if not main_row:
        conn.close()
        return None
    main_data = dict(main_row)
    main_data["full_analysis"] = json.loads(main_data["full_analysis"]) if main_data["full_analysis"] else []
    
    # 读取名字子表
    name_rows = conn.execute("SELECT * FROM search_name_item WHERE record_id = ?", (record_id,)).fetchall()
    name_list = []
    for r in name_rows:
        d = dict(r)
        d["source_tags"] = json.loads(d["source_tags"]) if d["source_tags"] else []
        name_list.append(d)
    
    # 关键缺失：把名字列表塞进主数据，前端才能读到
    main_data["suggestions"] = name_list
    conn.close()
    return main_data

# ==================== 收藏模块【已修复SQL绑定参数错误】 ====================
def add_collect(user_id, name, meaning, five_attr, record_id):
    conn = get_conn()
    # 修复前错误：WHERE user_id AND full_name = ?
    # 修复后：两个条件都加占位符，参数一一对应
    exist = conn.execute(
        "SELECT id FROM collect_name WHERE user_id = ? AND full_name = ?",
        (user_id, name)
    ).fetchone()
    if exist:
        conn.close()
        return False
    conn.execute("""
        INSERT INTO collect_name(user_id, full_name, meaning, five_attr, record_id)
        VALUES (?,?,?,?,?)
    """, (user_id, name, meaning, five_attr, record_id))
    conn.commit()
    conn.close()
    return True

def get_user_collect_list(user_id):
    conn = get_conn()
    res = conn.execute("SELECT * FROM collect_name WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return [dict(i) for i in res]

def batch_del_collect(user_id, del_ids):
    conn = get_conn()
    place = ",".join(["?"]*len(del_ids))
    sql = f"DELETE FROM collect_name WHERE user_id = ? AND id IN ({place})"
    conn.execute(sql, [user_id] + del_ids)
    conn.commit()
    conn.close()

# 新增：根据用户ID+名字 删除单条收藏（取消收藏专用）
def remove_collect_item(user_id, full_name):
    conn = get_conn()
    sql = "DELETE FROM collect_name WHERE user_id = ? AND full_name = ?"
    conn.execute(sql, (user_id, full_name))
    conn.commit()
    conn.close()

# ==================== 词库诗词 ====================
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