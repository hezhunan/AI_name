import sys
import os
sys.stdout.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"
import sqlite3
import json

DB_PATH = "db.db"

def get_conn():
    # 开启WAL多端并发，超时10秒避免锁库阻塞
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
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
        print(f"✅ 注册成功 账号:{account} 用户名:{username}")
        return True
    except sqlite3.IntegrityError:
        print(f"❌ 注册失败：手机号{account}已存在")
        return False
    except Exception as e:
        print(f"❌ 注册数据库异常：{str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

        # ========== 重置用户密码 ==========
def reset_user_password(account, new_pwd):
    """根据手机号账号修改密码，返回是否修改成功"""
    conn = get_conn()
    # 先判断账号是否存在
    user = conn.execute("SELECT id FROM user WHERE account = ?", (account,)).fetchone()
    if not user:
        conn.close()
        return False, "该手机号账号不存在"
    # 更新密码
    conn.execute("UPDATE user SET password = ? WHERE account = ?", (new_pwd, account))
    conn.commit()
    conn.close()
    return True, "密码重置成功"

# ==================== 起名记录存储 ====================
def add_full_search_record(user_id, input_data, pillar, analysis):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO search_record (
                user_id, surname, gender, birth,
                pillar_year, pillar_month, pillar_day, pillar_hour,
                zodiac, time_period, birth_element, balance, full_analysis,
                need_words, avoid_words, style_prefer
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            json.dumps(analysis["balance"], ensure_ascii=False, default=str),
            json.dumps(analysis["full_analysis"], ensure_ascii=False, default=str),
            input_data.get("need_words", "无"),
            input_data.get("avoid_words", "无"),
            input_data.get("style_prefer", "简约")
        ))
        record_id = cur.lastrowid
        # 批量插入每条推荐名字
        for item in analysis["suggestions"]:
            cur.execute("""
                INSERT INTO search_name_item (record_id, name, meaning, source_tags, wuge_info)
                VALUES (?,?,?,?,?)
            """, (
                record_id,
                item["name"],
                item["meaning"],
                json.dumps(item["source_tags"], ensure_ascii=False, default=str),
                json.dumps(item.get("wuge_info", {}), ensure_ascii=False, default=str)
            ))
        conn.commit()
        print(f"DB写入成功 记录{record_id} 用户{user_id}")
        return record_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# 根据用户ID获取所有历史起名
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

# 单条完整记录详情
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
    name_rows = conn.execute("SELECT * FROM search_name_item WHERE record_id = ?", (record_id,)).fetchall()
    name_list = []
    for r in name_rows:
        d = dict(r)
        d["source_tags"] = json.loads(d["source_tags"]) if d["source_tags"] else []
        # 关键：解析wuge_info
        d["wuge_info"] = json.loads(d["wuge_info"]) if d["wuge_info"] else {}
        name_list.append(d)
    main_data["suggestions"] = name_list
    conn.close()
    return main_data

# ==================== 收藏模块 ====================
# 原：def add_collect(user_id, name, meaning, five_attr, record_id):
# 修改为增加wuge参数
def add_collect(user_id, name, meaning, five_attr, record_id, wuge_info=None):
    conn = get_conn()
    exist = conn.execute(
        "SELECT id FROM collect_name WHERE user_id = ? AND full_name = ?",
        (user_id, name)
    ).fetchone()
    if exist:
        conn.close()
        return False
    wuge_str = json.dumps(wuge_info, ensure_ascii=False) if wuge_info is not None else None
    conn.execute("""
        INSERT INTO collect_name(user_id, full_name, meaning, five_attr, record_id, wuge_info)
        VALUES (?,?,?,?,?,?)
    """, (user_id, name, meaning, five_attr, record_id, wuge_str))
    conn.commit()
    conn.close()
    return True

def get_user_collect_list(user_id):
    conn = get_conn()
    res = conn.execute("SELECT id, full_name, meaning, five_attr, wuge_info FROM collect_name WHERE user_id = ?", (user_id,)).fetchall()
    arr = []
    for i in res:
        d = dict(i)
        if d["wuge_info"]:
            d["wuge_info"] = json.loads(d["wuge_info"])
        else:
            d["wuge_info"] = None
        arr.append(d)
    conn.close()
    return arr

def batch_del_collect(user_id, del_ids):
    conn = get_conn()
    place = ",".join(["?"] * len(del_ids))
    sql = f"DELETE FROM collect_name WHERE user_id = ? AND id IN ({place})"
    conn.execute(sql, [user_id] + del_ids)
    conn.commit()
    conn.close()

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

# 修改用户名、密码
def update_user_info(user_id, username, password):
    conn = sqlite3.connect("db.db")
    cur = conn.cursor()
    sql_parts = []
    params = []
    if username:
        sql_parts.append("username = ?")
        params.append(username)
    if password:
        sql_parts.append("password = ?")
        params.append(password)
    params.append(user_id)
    sql = f"UPDATE user SET {','.join(sql_parts)} WHERE id = ?"
    cur.execute(sql, params)
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0

# 注销账号：删除用户+全部收藏+全部起名记录+起名子记录
def delete_user_all_related(uid):
    conn = get_conn()
    cur = conn.cursor()
    try:
        # 1 删除收藏
        cur.execute("DELETE FROM collect_name WHERE user_id = ?", (uid,))
        # 2 查询该用户所有起名记录ID
        record_list = cur.execute("SELECT id FROM search_record WHERE user_id = ?", (uid,)).fetchall()
        record_ids = [row["id"] for row in record_list]
        # 3 删除起名详情子数据
        if record_ids:
            placeholder = ",".join(["?"] * len(record_ids))
            cur.execute(f"DELETE FROM search_name_item WHERE record_id IN ({placeholder})", record_ids)
        # 4 删除主起名记录
        cur.execute("DELETE FROM search_record WHERE user_id = ?", (uid,))
        # 5 删除用户本身
        cur.execute("DELETE FROM user WHERE id = ?", (uid,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print("注销清空数据失败：", e)
        return False
    finally:
        conn.close()