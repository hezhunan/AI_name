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

# 批量删除收藏
@api_bp.route("/collect/batch_del", methods=["POST"])
def batch_del():
    d = request.get_json()
    db.batch_del_col(d["user_id"], d["del_ids"])
    return jsonify({"code":200, "msg":"删除成功"})

# 简易浏览记录列表
@api_bp.route("/search/list", methods=["POST"])
def search_list():
    uid = request.get_json()["user_id"]
    return jsonify({"code":200, "data":db.get_user_search_list(uid)})

# 完整记录详情接口
@api_bp.route("/search/detail", methods=["POST"])
def search_detail():
    d = request.get_json()
    data = db.get_full_search_by_record_id(d["record_id"], d["user_id"])
    if not data:
        return jsonify({"code":400, "msg":"无记录"})
    return jsonify({"code":200, "data":data})