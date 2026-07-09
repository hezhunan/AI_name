import sys
import os
sys.stdout.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"
import sqlite3
from flask import Blueprint, request, jsonify
import db

api_bp = Blueprint("api", __name__)

# 登录接口
@api_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    account = data.get("account", "").strip()
    password = data.get("password", "").strip()
    user = db.get_user_by_account(account)
    if not user:
        return jsonify({"code":400,"msg":"账号不存在"})
    if user["password"] != password:
        return jsonify({"code":400,"msg":"密码错误"})
    return jsonify({
        "code":200,
        "msg":"登录成功",
        "user_id":user["id"],
        "username":user["username"],
        "account":user["account"]
    })

# 注册账号接口
@api_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    account = data.get("account", "").strip()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    # 基础校验
    if len(account) != 11 or not account.isdigit():
        return jsonify({"code":400, "msg":"账号必须为11位手机号"})
    if not username or not password:
        return jsonify({"code":400, "msg":"用户名和密码不能为空"})
    # 调用db新增用户
    success = db.add_user(account, username, password)
    if success:
        return jsonify({"code":200, "msg":"注册成功，请前往登录"})
    else:
        return jsonify({"code":400, "msg":"该手机号已注册"})

# 添加收藏
@api_bp.route("/collect/add", methods=["POST"])
def collect_add():
    d = request.get_json()
    ok = db.add_collect(d["user_id"], d["full_name"], d["meaning"], d["five_attr"], d["record_id"])
    return jsonify({"code":200 if ok else 400, "msg":"收藏成功" if ok else "已收藏"})

# 获取收藏列表
@api_bp.route("/collect/list", methods=["POST"])
def collect_list():
    uid = request.get_json()["user_id"]
    return jsonify({"code":200, "data":db.get_user_collect_list(uid)})

# 单条取消收藏
@api_bp.route("/collect/remove", methods=["POST"])
def collect_remove():
    data = request.get_json()
    user_id = data.get("user_id", 0)
    full_name = data.get("full_name", "")
    if not user_id or not full_name:
        return jsonify({"code":400, "msg":"参数缺失"})
    db.remove_collect_item(user_id, full_name)
    return jsonify({"code":200, "msg":"取消收藏成功"})

# 批量删除收藏
@api_bp.route("/collect/batch_del", methods=["POST"])
def collect_batch_del():
    data = request.get_json()
    user_id = data.get("user_id", 0)
    del_ids = data.get("del_ids", [])
    if not isinstance(del_ids, list) or len(del_ids) == 0:
        return jsonify({"code": 400, "msg": "无删除ID"})
    db.batch_del_collect(user_id, del_ids)
    return jsonify({"code": 200, "msg": "删除成功"})

# 获取起名历史列表
@api_bp.route("/search/list", methods=["POST"])
def search_list():
    uid = request.get_json()["user_id"]
    return jsonify({"code":200, "data":db.get_user_search_list(uid)})

# 单条起名完整详情
@api_bp.route("/search/detail", methods=["POST"])
def search_detail():
    try:
        d = request.get_json()
        user_id = d.get("user_id", 0)
        record_id = d.get("record_id", 0)
        if not user_id or not record_id:
            return jsonify({"code":400, "msg":"缺少用户ID或记录ID"})
        data = db.get_full_search_by_record_id(record_id, user_id)
        if not data:
            return jsonify({"code":400, "msg":"该记录不存在"})
        data["year"] = data["pillar_year"]
        data["month"] = data["pillar_month"]
        data["day"] = data["pillar_day"]
        data["hour"] = data["pillar_hour"]
        return jsonify({"code":200, "data":data})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"code":500, "msg":"服务器查询异常"})
    
# 新增：忘记密码重置接口
@api_bp.route("/reset_pwd", methods=["POST"])
def reset_pwd():
    data = request.get_json() if request.is_json else request.form
    account = data.get("account", "").strip()
    new_pwd = data.get("new_pwd", "").strip()
    confirm_pwd = data.get("confirm_pwd", "").strip()

    # 参数校验
    if len(account) != 11 or not account.isdigit():
        return jsonify({"code":400, "msg":"账号必须为11位手机号"})
    if not new_pwd or not confirm_pwd:
        return jsonify({"code":400, "msg":"密码不能为空"})
    if new_pwd != confirm_pwd:
        return jsonify({"code":400, "msg":"两次输入密码不一致"})
    
    # 调用db更新密码
    ok, msg = db.reset_user_password(account, new_pwd)
    if ok:
        return jsonify({"code":200, "msg":msg})
    else:
        return jsonify({"code":400, "msg":msg})
    
# 修改用户信息接口
@api_bp.route("/user/update_info", methods=["POST"])
def user_update_info():
    data = request.get_json()
    user_id = data.get("user_id", 0)
    if not user_id:
        return jsonify({"code": 400, "msg": "用户ID不能为空"})
    new_name = data.get("username", "").strip()
    new_pwd = data.get("password", "").strip()
    # 至少传一项才能修改
    if not new_name and not new_pwd:
        return jsonify({"code": 400, "msg": "请填写需要修改的内容"})
    # 调用db，按需更新
    res = db.update_user_info(user_id, new_name, new_pwd)
    return jsonify({"code": 200 if res else 400, "msg": "修改成功" if res else "修改失败"})

# 注销账号，清空用户全部数据接口
@api_bp.route("/user/destroy_all", methods=["POST"])
def user_destroy_all():
    data = request.get_json()
    user_id = data.get("user_id", 0)
    if not user_id:
        return jsonify({"code": 400, "msg": "用户ID缺失"})
    res = db.delete_user_all_related(user_id)
    return jsonify({"code": 200 if res else 400, "msg": "账号已注销，数据全部清除" if res else "注销失败"})