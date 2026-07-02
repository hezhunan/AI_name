from flask import Blueprint, request, jsonify
import re
import db

# 创建接口蓝图
api_bp = Blueprint("api", __name__)

# 11位纯数字手机号正则校验规则
PHONE_REG = re.compile(r'^\d{11}$')

# ===================== 用户注册接口 =====================
@api_bp.route("/register", methods=["POST"])
def register():
    # 获取前端JSON参数
    data = request.get_json()
    account = data.get("account", "").strip()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    # 非空校验
    if not account or not username or not password:
        return jsonify({"code": 400, "msg": "账号、用户名、密码不能为空"})
    # 手机号格式校验
    if not PHONE_REG.match(account):
        return jsonify({"code": 400, "msg": "登录账号必须是11位纯数字手机号"})

    # 调用数据库注册方法
    result = db.add_user(account, username, password)
    if result:
        return jsonify({"code": 200, "msg": "注册成功"})
    else:
        return jsonify({"code": 400, "msg": "该手机号账号已注册"})

# ===================== 用户登录接口 =====================
@api_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    account = data.get("account", "").strip()
    password = data.get("password", "").strip()

    # 非空校验
    if not account or not password:
        return jsonify({"code": 400, "msg": "账号和密码不能为空"})
    # 手机号格式校验
    if not PHONE_REG.match(account):
        return jsonify({"code": 400, "msg": "账号格式错误，请输入11位手机号"})

    # 查询用户
    user_info = db.get_user_by_account(account)
    if user_info and user_info["password"] == password:
        # 登录成功，返回用户信息
        return jsonify({
            "code": 200,
            "user_id": user_info["id"],
            "username": user_info["username"],
            "account": user_info["account"]
        })
    return jsonify({"code": 400, "msg": "账号或密码错误"})

# ===================== 保存起名搜索记录接口 =====================
@api_bp.route("/save_search", methods=["POST"])
def save_search():
    data = request.get_json()
    uid = data["uid"]
    surname = data["surname"]
    gender = data["gender"]
    birth = data["birth"]
    record_id = db.add_search_record(uid, surname, gender, birth)
    return jsonify({"code": 200, "record_id": record_id})

# ===================== 获取用户全部搜索历史 =====================
@api_bp.route("/search_list/<int:uid>", methods=["GET"])
def search_list(uid):
    record_list = db.get_user_search(uid)
    return jsonify({"code": 200, "data": record_list})

# ===================== 添加名字收藏接口 =====================
@api_bp.route("/add_collect", methods=["POST"])
def add_collect():
    data = request.get_json()
    db.add_collect(
        data["uid"],
        data["name"],
        data["meaning"],
        data["five"],
        data["record_id"]
    )
    return jsonify({"code": 200, "msg": "收藏成功"})

# ===================== 删除收藏接口 =====================
@api_bp.route("/del_collect", methods=["POST"])
def del_collect():
    data = request.get_json()
    db.del_collect(data["uid"], data["cid"])
    return jsonify({"code": 200, "msg": "取消收藏"})

# ===================== 获取用户全部收藏 =====================
@api_bp.route("/collect_list/<int:uid>", methods=["GET"])
def collect_list(uid):
    collect_list = db.get_user_collect(uid)
    return jsonify({"code": 200, "data": collect_list})