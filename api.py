import sys
import os
sys.stdout.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"
from flask import Blueprint, request, jsonify
import re
import db

api_bp = Blueprint("api", __name__)

# 登录
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
    

# 添加收藏
@api_bp.route("/collect/add", methods=["POST"])
def collect_add():
    d = request.get_json()
    ok = db.add_collect(d["user_id"], d["full_name"], d["meaning"], d["five_attr"], d["record_id"])
    return jsonify({"code":200 if ok else 400, "msg":"收藏成功" if ok else "已收藏"})

# 收藏列表
@api_bp.route("/collect/list", methods=["POST"])
def collect_list():
    uid = request.get_json()["user_id"]
    return jsonify({"code":200, "data":db.get_user_collect_list(uid)})

# 新增取消收藏接口
@api_bp.route("/collect/remove", methods=["POST"])
def collect_remove():
    data = request.get_json()
    user_id = data.get("user_id", 0)
    full_name = data.get("full_name", "")
    if not user_id or not full_name:
        return jsonify({"code":400, "msg":"参数缺失"})
    # 只传user_id和名字
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
    # 调用db函数执行数据库DELETE
    db.batch_del_collect(user_id, del_ids)
    return jsonify({"code": 200, "msg": "删除成功"})

# 简易浏览记录列表
@api_bp.route("/search/list", methods=["POST"])
def search_list():
    uid = request.get_json()["user_id"]
    return jsonify({"code":200, "data":db.get_user_search_list(uid)})

# 完整记录详情接口
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
        # 四柱字段兼容前端
        data["year"] = data["pillar_year"]
        data["month"] = data["pillar_month"]
        data["day"] = data["pillar_day"]
        data["hour"] = data["pillar_hour"]
        print("接口返回完整data：", data) # 打印调试，看是否包含suggestions
        return jsonify({"code":200, "data":data})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"code":500, "msg":"服务器查询异常"})