# 解决Windows中文编码报错，放在文件最顶部
import sys
import os
sys.stdout.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"
from flask import Flask, render_template, request, jsonify, redirect
import random
import json
import traceback
import db
from api import api_bp
from zhipuai import ZhipuAI
from datetime import datetime, date
import calendar

app = Flask(__name__)

# 智谱AI密钥
ZHIPU_API_KEY = "00e172fcad8844afae3531c0123758eb.LWb2F0bsOK2IOd1n"
client = ZhipuAI(api_key=ZHIPU_API_KEY)

# 天干地支常量
TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
ZODIAC_MAP = {
    "子": "鼠", "丑": "牛", "寅": "虎", "卯": "兔",
    "辰": "龙", "巳": "蛇", "午": "马", "未": "羊",
    "申": "猴", "酉": "鸡", "戌": "狗", "亥": "猪"
}

# 节气表
SOLAR_TERM_DAY = {
    1: [4, 19],2: [3, 18],3: [5, 20],4: [4, 20],
    5: [5, 21],6: [5, 21],7: [7, 22],8: [7, 23],
    9: [7, 23],10: [8, 24],11: [7, 22],12: [6, 21],
}

# 时辰对照表
SHI_CHEN_MAP = [
    ("子", 23, 0), ("丑", 1, 2), ("寅", 3, 4), ("卯", 5, 6),
    ("辰", 7, 8), ("巳", 9, 10), ("午", 11, 12), ("未", 13, 14),
    ("申", 15, 16), ("酉", 17, 18), ("戌", 19, 20), ("亥", 21, 22)
]

def get_year_gz(year):
    base = 4
    idx = (year - base) % 60
    g = idx % 10
    z = idx % 12
    return TIAN_GAN[g] + DI_ZHI[z]

def get_month_gz(year, month, day):
    year_g = get_year_gz(year)[0]
    year_g_idx = TIAN_GAN.index(year_g)
    m_base = [2, 4, 6, 8, 0, 2, 4, 6, 8, 0, 2, 4]
    m_start_idx = m_base[year_g_idx]
    cut_day = SOLAR_TERM_DAY[month][0]
    if day >= cut_day:
        m_idx = m_start_idx + month - 1
    else:
        m_idx = m_start_idx + month - 2
    g = m_idx % 10
    z = (month - 1) % 12
    return TIAN_GAN[g] + DI_ZHI[z]

def get_day_gz(year, month, day):
    base_date = date(2000, 1, 1)
    target = date(year, month, day)
    delta = (target - base_date).days
    base_gz = 16
    total = base_gz + delta
    g = total % 10
    z = total % 12
    return TIAN_GAN[g] + DI_ZHI[z]

def get_shichen_gz(year, month, day, hour):
    day_gz_str = get_day_gz(year, month, day)
    if not day_gz_str or len(day_gz_str) < 1:
        day_gz_str = "甲子"
    day_g = day_gz_str[0]
    if day_g not in TIAN_GAN:
        day_g = "甲"
    day_g_idx = TIAN_GAN.index(day_g)
    shi_base = [0, 2, 4, 6, 8, 0, 2, 4, 6, 8]
    shi_start = shi_base[day_g_idx]
    shi_zhi = ""
    for z_name, h1, h2 in SHI_CHEN_MAP:
        if h1 <= hour <= h2:
            shi_zhi = z_name
            break
    if not shi_zhi:
        shi_zhi = "子"
    z_idx = DI_ZHI.index(shi_zhi)
    g_idx = (shi_start + z_idx) % 10
    return TIAN_GAN[g_idx] + shi_zhi, shi_zhi

def get_full_birth_pillar(dt: datetime):
    y = dt.year
    m = dt.month
    d = dt.day
    h = dt.hour
    year_zhu = get_year_gz(y)
    # 修复：补齐第三个参数 d
    month_zhu = get_month_gz(y, m, d)
    day_zhu = get_day_gz(y, m, d)
    shi_zhu, shi_zhi = get_shichen_gz(y, m, d, h)
    zodiac = ZODIAC_MAP[year_zhu[1]]
    hour_text = f"{h}时"
    return {
        "year": year_zhu,
        "month": month_zhu,
        "day": day_zhu,
        "hour": shi_zhu,
        "zodiac": zodiac,
        "time_period": hour_text
    }

# 兜底本地起名
def local_fallback_name(surname, target_five):
    words = db.get_five_words(target_five)
    poems = db.get_all_poems()
    res = []
    for _ in range(3):
        w1 = random.choice(words)
        w2 = random.choice(words)
        full = surname + w1 + w2
        poem = random.choice(poems)
        mean = f"出自诗句：{poem}，五行属{target_five}，寓意平安顺遂、前程明朗"
        res.append({
            "name": full,
            "meaning": mean,
            "source_tags": [f"喜用神{target_five}", "古风清雅"]
        })
    return res

# AI八字起名
def glm_analysis_name(surname, gender, pillar_info):
    print("===== Start Zhipu GLM API Call =====")
    print(f"Params: surname={surname}, gender={gender}, pillar={pillar_info}")
    system_prompt = """
你是专业传统八字命理起名大师，四柱八字已由系统精准计算完毕，你只负责分析旺衰、确定唯一喜用神、生成全新不重复名字。
硬性强制规则，必须严格遵守：
1. 给定四柱不可修改，只基于固定八字分析；
2. 根据八字旺衰得出唯一喜用神（金/木/水/火/土其中一个）；
3. 【最重要】每次调用必须生成**完全不同、从未出现过**的3个双字名字，禁止复用之前生成过的字词、组合；
4. 名字风格不局限古诗词，支持两种路线自由穿插搭配：
   ① 国风雅致款；② 现代简约干净清爽款，两种风格随机混合，兼顾传统与当代审美；
5. 男名大气开阔、格局宏大；女名温婉柔和、干净清新；
6. 标签不再固定「喜用神+风格+性别」三要素，可从多维度自由挑选组合，可选维度包含：
   五行适配喜用神、音律顺口好听、字形简洁美观、寓意格局宏大、温柔治愈、清冷高级、小众不烂大街、利于学业、事业前程、温润内敛、阳光开朗、国风古韵、现代简约、文雅书卷气等；
   每个名字标签数量2~4个即可，维度随机多样化，不要全部统一模板；
7. 每个名字的寓意、解读文案全部独立，措辞差异化，杜绝重复套话；
8. 输出仅纯净JSON，无任何多余文字、注释、换行、markdown；

JSON固定结构：
{
    "birth_element": "单一五行字（金/木/水/火/土）",
    "balance": "完整八字分析，说明日主旺衰、全局五行格局、为何取该喜用神，文案每次措辞微调，不要完全复制上一次",
    "full_analysis": [
        "年柱单独解读（措辞微调，避免完全重复）",
        "月柱单独解读（措辞微调，避免完全重复）",
        "日柱日主解读（措辞微调，避免完全重复）",
        "时柱运势解读（措辞微调，避免完全重复）"
    ],
    "suggestions": [
        {
            "name": "全新双字全名，不可与过往生成重复",
            "meaning": "完整名字寓意，现代名侧重氛围感、简约干净，国风名可搭配浅淡典故，文案独一无二",
            "source_tags": ["多维度自由标签，不强制固定三类模板，2-4个标签随机组合"]
        }
    ]
}
约束：
- full_analysis 固定4条；suggestions固定3个名字；
- 严禁重复名字、重复寓意、重复标签文案；
- 绝对不允许修改传入的四柱干支，仅做命理分析起名。
"""
    user_prompt = f"""
姓氏：{surname}
性别：{gender}（male=男，female=女）
已精准排盘四柱：
年柱：{pillar_info['year']}
月柱：{pillar_info['month']}
日柱：{pillar_info['day']}
时柱：{pillar_info['hour']}
本次生成3个全新无重复名字，可现代简约也可国风雅致；标签采用多维度多元化搭配，不要统一套用「喜用神+风格+性别」固定模板，严格输出纯JSON，不要额外文字说明。
"""
    try:
        response = client.chat.completions.create(
            model="glm-5.2",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        model_content = response.choices[0].message.content.strip()
        print("Model raw output:", model_content)
        data = json.loads(model_content)
        valid_five = ["金", "木", "水", "火", "土"]
        if data.get("birth_element") not in valid_five:
            raise Exception("模型返回五行不合法")
        data["year"] = pillar_info["year"]
        data["month"] = pillar_info["month"]
        data["day"] = pillar_info["day"]
        data["hour"] = pillar_info["hour"]
        return data
    except Exception as e:
        print(f"Zhipu API Exception: {str(e)}")
        fallback_five = random.choice(["金", "木", "水", "火", "土"])
        fallback_suggest = local_fallback_name(surname, fallback_five)
        return {
            "birth_element": fallback_five,
            "balance": f"AI解析异常，启用备用起名库，临时喜用神为{fallback_five}",
            "year": pillar_info["year"],
            "month": pillar_info["month"],
            "day": pillar_info["day"],
            "hour": pillar_info["hour"],
            "full_analysis": [
                f"年柱{pillar_info['year']}，主导早年根基与祖辈运势",
                f"月柱{pillar_info['month']}，主管青年时期、家庭环境",
                f"日柱{pillar_info['day']}，日主自身，代表一生核心性格",
                f"时柱{pillar_info['hour']}，管晚年子女、终局运势"
            ],
            "suggestions": fallback_suggest
        }

# ====================== 页面路由（仅渲染HTML，无API接口） ======================
@app.route("/")
def root_redirect():
    return redirect("/login")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/register")
def register_page():
    return render_template("register.html")

# 起名首页：双重UID（Cookie+前端隐藏域兜底，多端登录兼容）
@app.route("/index", methods=["GET", "POST"])
def index_page():
    result = None
    error = None
    current_record_id = 0
    db_bazi = {} # 顶层数据库标准八字变量，页面优先渲染这个
    input_pillar = {}
    if request.method == "POST":
        sur = request.form.get("surname", "").strip()
        gender = request.form.get("gender")
        birth_str = request.form.get("birth")
        front_login_uid = request.form.get("front_login_uid", "")
        if not sur or not birth_str:
            error = "姓氏与出生时间不能为空"
        else:
            birth_dt = datetime.strptime(birth_str, "%Y-%m-%dT%H:%M")
            pillar = get_full_birth_pillar(birth_dt)
            input_pillar = pillar
            ai_res = glm_analysis_name(sur, gender, pillar)
            login_uid = request.cookies.get("loginUid", "")
            real_uid = 0
            if login_uid.isdigit():
                real_uid = int(login_uid)
            elif front_login_uid.isdigit():
                real_uid = int(front_login_uid)
            
            current_record_id = 0
            # 1、写入数据库（和user历史记录存储逻辑完全一致）
            if real_uid > 0:
                try:
                    input_info = {"surname":sur,"gender":gender,"birth":birth_str}
                    analysis_info = {
                        "birth_element": ai_res["birth_element"],
                        "balance": ai_res["balance"],
                        "full_analysis": ai_res["full_analysis"],
                        "suggestions": ai_res["suggestions"]
                    }
                    current_record_id = db.add_full_search_record(real_uid, input_info, pillar, analysis_info)
                except Exception as e:
                    traceback.print_exc()
            
            # 2、【核心复刻user页面】从数据库重读完整标准化记录
            if current_record_id > 0 and real_uid > 0:
                db_full = db.get_full_search_by_record_id(current_record_id, real_uid)
                if db_full:
                    # 和user接口统一标准化字段
                    db_bazi = {
                        "year": db_full["pillar_year"],
                        "month": db_full["pillar_month"],
                        "day": db_full["pillar_day"],
                        "hour": db_full["pillar_hour"],
                        "zodiac": pillar["zodiac"],
                        "birth_element": db_full["birth_element"],
                        "balance": db_full["balance"],
                        "full_analysis": db_full["full_analysis"]
                    }
                    result = {
                        "input":{"surname":sur,"gender":gender,"birth":birth_str},
                        "bazi": db_bazi,
                        "time_period":pillar["time_period"],
                        "suggestions":db_full["suggestions"],
                        "record_id":current_record_id
                    }
            else:
                # 游客无账号，兜底AI数据
                db_bazi = {
                    "year": ai_res["year"],
                    "month": ai_res["month"],
                    "day": ai_res["day"],
                    "hour": ai_res["hour"],
                    "zodiac": pillar["zodiac"],
                    "birth_element": ai_res["birth_element"],
                    "balance": ai_res["balance"],
                    "full_analysis": ai_res["full_analysis"]
                }
                result = {
                    "input":{"surname":sur,"gender":gender,"birth":birth_str},
                    "bazi": db_bazi,
                    "time_period":pillar["time_period"],
                    "suggestions":ai_res["suggestions"],
                    "record_id":0
                }
    # 单独把数据库来源八字db_bazi传给页面，最高优先级渲染
    return render_template("index.html", result=result, error=error, db_bazi=db_bazi)

# 游客页面完全保留，不改动任何逻辑
@app.route("/tourist", methods=["GET", "POST"])
def tourist_page():
    result = None
    error = None
    render_bazi = {}
    if request.method == "POST":
        sur = request.form.get("surname", "").strip()
        gender = request.form.get("gender")
        birth_str = request.form.get("birth")
        if not sur or not birth_str:
            error = "姓氏与出生时间不能为空"
        else:
            birth_dt = datetime.strptime(birth_str, "%Y-%m-%dT%H:%M")
            pillar = get_full_birth_pillar(birth_dt)
            ai_res = glm_analysis_name(sur, gender, pillar)
            render_bazi = {
                "year": ai_res["year"],
                "month": ai_res["month"],
                "day": ai_res["day"],
                "hour": ai_res["hour"],
                "zodiac": pillar["zodiac"],
                "birth_element": ai_res["birth_element"],
                "balance": ai_res["balance"],
                "full_analysis": ai_res["full_analysis"]
            }
            result = {
                "input":{"surname":sur,"gender":gender,"birth":birth_str},
                "bazi":render_bazi,
                "time_period":pillar["time_period"],
                "suggestions":ai_res["suggestions"]
            }
    return render_template("tourist.html", result=result, error=error, bazi=render_bazi)

@app.route("/user")
def user_center():
    login_uid = request.cookies.get("loginUid", "")
    username = "游客"
    try:
        if login_uid.isdigit():
            uid = int(login_uid)
            user_info = db.get_user_by_id(uid)
            if user_info and "username" in user_info:
                username = user_info["username"]
    except Exception as e:
        username = "游客"
    return render_template("user.html", username=username)

# 新增：忘记密码重置页面路由
@app.route("/reset_pwd", methods=["GET", "POST"])
def reset_pwd_page():
    msg = ""
    msg_type = ""
    if request.method == "POST":
        # 表单提交，转发API逻辑，简易页面提示
        import requests
        try:
            res = requests.post("http://127.0.0.1:5000/api/reset_pwd", data=request.form)
            res_data = res.json()
            if res_data["code"] == 200:
                msg = res_data["msg"]
                msg_type = "success"
            else:
                msg = res_data["msg"]
                msg_type = "error"
        except Exception as e:
            msg = "服务器异常，重置失败"
            msg_type = "error"
    return render_template("reset_pwd.html", msg=msg, msg_type=msg_type)

# ========== 所有路由写完后，最后注册蓝图，解决AssertionError报错 ==========
app.register_blueprint(api_bp, url_prefix="/api")

# 关键：host=0.0.0.0 局域网手机/平板全部可访问，实现多端共用数据库
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)