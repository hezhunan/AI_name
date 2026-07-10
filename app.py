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
ZHIPU_API_KEY = "a7afddb044ef4948bea53f4c0771f2bc.ajrCfwEf9I2jGbY5"
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
    month_zhu = get_month_gz(y, m, d)
    day_zhu = get_day_gz(y, m, d)
    # 修复：补齐第四个参数 h
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
    wuge_comments = [
        "五格配置平顺，数理中性偏吉，仅作民俗参考",
        "三才搭配均衡，传统五格学说中属上等配置，仅供娱乐",
        "五格略有起伏，不影响八字核心格局，无需介意"
    ]
    for i in range(3):
        w1 = random.choice(words)
        w2 = random.choice(words)
        full = surname + w1 + w2
        poem = random.choice(poems)
        mean = f"出自诗句：{poem}，五行属{target_five}，贴合八字喜用神与生肖宜忌，寓意平安顺遂、前程明朗"
        # 模拟随机五格数字
        wuge = {
            "tian": random.randint(8,16),
            "ren": random.randint(12,28),
            "di": random.randint(10,26),
            "zong": random.randint(15,32),
            "wai": random.randint(5,14),
            "comment": wuge_comments[i]
        }
        res.append({
            "name": full,
            "meaning": mean,
            "source_tags": [f"喜用神{target_five}", "古风清雅"],
            "wuge_info": wuge
        })
    return res

# AI八字起名【修复：新增三个入参】
def glm_analysis_name(surname, gender, pillar_info, need_words, avoid_words, style_prefer):
    print("===== Start Zhipu GLM API Call =====")
    print(f"Params: surname={surname}, gender={gender}, pillar={pillar_info}")
    system_prompt = """
你是专业传统八字命理起名大师，四柱八字已由系统精准计算完毕，起名优先级严格遵循：
【第一优先级（硬性强制）】八字日主旺衰分析、唯一喜用神五行适配、对应生肖用字宜忌；
【第二优先级（辅助参考，不强制过滤）】三才五格数理配置，仅作为附加展示，不淘汰不符合五格的名字。
硬性强制规则，必须严格遵守：
1. 给定四柱不可修改，只基于固定八字分析；
2. 根据八字旺衰得出唯一喜用神（金/木/水/火/土其中一个），优先挑选五行完全匹配喜用神、适配生肖宜忌的汉字组合；
3. 【最重要】每次调用必须生成**完全不同、从未出现过**的3个双字/单字全名，禁止复用过往生成的字词、组合；
4. 起名严格遵循用户指定的单一风格，仅支持以下三类，不得混搭：
   ① 诗意国风款：取自诗词古文，意境清雅含蓄，书卷感浓厚，用字古典雅致；
   ② 简约干净款：现代清爽极简，字形简单好写，读音柔和顺口，无生僻冷字；
   ③ 大气开阔款：格局恢弘辽阔，字义沉稳厚重，适合凸显胸襟前程，气场舒展；
   收到用户传入的风格偏好后，3个名字全部统一贴合该风格，禁止跨风格混杂；
5. 性别区分严格：男名偏向大气开阔、沉稳有格局；女名偏向温婉柔和、干净清雅；
6. 标签不固定「喜用神+风格+性别」模板，多维度自由搭配，可选维度：
   五行适配喜用神、音律顺口好听、字形简洁美观、寓意格局宏大、温柔治愈、清冷高级、小众不烂大街、利于学业、事业前程、温润内敛、阳光开朗、国风古韵、现代简约、文雅书卷气、三才五格吉利等；
   每个名字标签2~4个，随机多样化，不要全部统一；
7. 每个名字寓意解读完全独立、措辞差异化，杜绝套话重复；
8. 每条名字必须附带完整三才五格解析：天格、人格、地格、总格、外格数字+简短吉凶评语；
9. 仅输出纯净JSON，无多余文字、注释、换行、markdown、解释语句；

JSON固定结构：
{
    "birth_element": "单一五行字（金/木/水/火/土）",
    "balance": "完整八字分析，说明日主旺衰、全局五行格局、取该喜用神的原因，文案每次微调不重复，重点点明生肖用字宜忌",
    "full_analysis": [
        "年柱单独解读（措辞微调，避免完全重复）",
        "月柱单独解读（措辞微调，避免完全重复）",
        "日柱日主解读（措辞微调，避免完全重复）",
        "时柱运势解读（措辞微调，避免完全重复）"
    ],
    "suggestions": [
        {
            "name": "全新全名，不可与历史生成重复",
            "meaning": "专属名字寓意，贴合指定风格，国风款可搭配浅淡诗词典故，简约款侧重清爽氛围感，大气款突出格局前程，文案独一无二",
            "source_tags": ["2-4个多维度标签，随机组合，不使用固定模板"],
            "wuge_info": {
                "tian": "天格数字",
                "ren": "人格数字",
                "di": "地格数字",
                "zong": "总格数字",
                "wai": "外格数字",
                "comment": "五格综合简评"
            }
        }
    ]
}
约束：
- full_analysis 固定4条；suggestions 固定3个名字；
- 严禁重复名字、重复寓意、重复标签文案；
- 绝对不可修改传入四柱干支，仅做命理分析；
- 起名核心为八字喜用神+生肖适配，五格仅附加展示，不淘汰名字；
- 全程严格匹配用户给定的单一风格，三个名字风格统一，禁止混搭多种风格。
"""
    user_prompt = f"""
姓氏：{surname}
性别：{gender}（male=男，female=女）
已精准排盘四柱：
年柱：{pillar_info['year']}
月柱：{pillar_info['month']}
日柱：{pillar_info['day']}
时柱：{pillar_info['hour']}
指定用字：{need_words}，若不是“无”，名字中尽量包含这些汉字；
避讳字：{avoid_words}，若不是“无”，所有名字严禁出现这些汉字；
风格偏好：{style_prefer}，严格贴合该风格起名；
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

# ====================== 页面路由 ======================
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
    db_bazi = {}
    input_pillar = {}
    # GET默认值，防止渲染报错
    need_words = "无"
    avoid_words = "无"
    style_prefer = "简约"

    if request.method == "POST":
        sur = request.form.get("surname", "").strip()
        gender = request.form.get("gender")
        birth_str = request.form.get("birth")
        # 读取表单参数
        need_words = request.form.get("need_words", "无").strip()
        avoid_words = request.form.get("avoid_words", "无").strip()
        style_prefer = request.form.get("style_prefer", "简约").strip()
        front_login_uid = request.form.get("front_login_uid", "")
        if not sur or not birth_str:
            error = "姓氏与出生时间不能为空"
        else:
            birth_dt = datetime.strptime(birth_str, "%Y-%m-%dT%H:%M")
            pillar = get_full_birth_pillar(birth_dt)
            input_pillar = pillar
            # 传入新增三个参数
            ai_res = glm_analysis_name(sur, gender, pillar, need_words, avoid_words, style_prefer)
            login_uid = request.cookies.get("loginUid", "")
            real_uid = 0
            if login_uid.isdigit():
                real_uid = int(login_uid)
            elif front_login_uid.isdigit():
                real_uid = int(front_login_uid)

            current_record_id = 0

            if real_uid > 0:
                try:
                    input_info = {
                        "surname": sur,
                        "gender": gender,
                        "birth": birth_str,
                        "need_words": need_words,
                        "avoid_words": avoid_words,
                        "style_prefer": style_prefer
                    }
                    analysis_info = {
                        "birth_element": ai_res["birth_element"],
                        "balance": ai_res["balance"],
                        "full_analysis": ai_res["full_analysis"],
                        "suggestions": ai_res["suggestions"]
                    }
                    current_record_id = db.add_full_search_record(real_uid, input_info, pillar, analysis_info)
                except Exception as e:
                    traceback.print_exc()

            if current_record_id > 0 and real_uid > 0:
                db_full = db.get_full_search_by_record_id(current_record_id, real_uid)
                if db_full:
                    db_bazi = {
                        "year": db_full["pillar_year"],
                        "month": db_full["pillar_month"],
                        "day": db_full["pillar_day"],
                        "hour": db_full["pillar_hour"],
                        "zodiac": pillar["zodiac"],
                        "birth_element": db_full["birth_element"],
                        "balance": db_full["balance"],
                        "full_analysis": db_full["full_analysis"],
                        "need_words": db_full["need_words"],
                        "avoid_words": db_full["avoid_words"],
                        "style_prefer": db_full["style_prefer"]
                    }
                    result = {
                        "input": {"surname": sur, "gender": gender, "birth": birth_str},
                        "bazi": db_bazi,
                        "time_period": pillar["time_period"],
                        "suggestions": db_full["suggestions"],
                        "record_id": current_record_id
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
                    "full_analysis": ai_res["full_analysis"],
                    "need_words": need_words,
                    "avoid_words": avoid_words,
                    "style_prefer": style_prefer
                }
                result = {
                    "input": {"surname": sur, "gender": gender, "birth": birth_str},
                    "bazi": db_bazi,
                    "time_period": pillar["time_period"],
                    "suggestions": ai_res["suggestions"],
                    "record_id": 0
                }
    return render_template("index.html", result=result, error=error, db_bazi=db_bazi)

# 游客页面【修复：修正变量笔误、多层兜底】
@app.route("/tourist", methods=["GET", "POST"])
def tourist_page():
    result = None
    error = None
    render_bazi = {
        "year": "", "month": "", "day": "", "hour": "", "zodiac": "",
        "birth_element": "", "balance": "", "full_analysis": [],
        "need_words": "无", "avoid_words": "无", "style_prefer": "简约"
    }
    need_words = "无"
    avoid_words = "无"
    style_prefer = "简约"
    if request.method == "POST":
        sur = request.form.get("surname", "").strip()
        gender = request.form.get("gender")
        birth_str = request.form.get("birth")
        need_words = request.form.get("need_words", "无").strip()
        avoid_words = request.form.get("avoid_words", "无").strip()
        style_prefer = request.form.get("style_prefer", "简约").strip()
        if not sur or not birth_str:
            error = "姓氏与出生时间不能为空"
        else:
            try:
                birth_dt = datetime.strptime(birth_str, "%Y-%m-%dT%H:%M")
                pillar = get_full_birth_pillar(birth_dt)
                ai_res = glm_analysis_name(sur, gender, pillar, need_words, avoid_words, style_prefer)
                # 修复变量笔误，兜底为空列表
                suggest_list = ai_res.get("suggestions", [])
                # 如果AI返回名字为空，强制生成备用名字
                if not suggest_list or len(suggest_list) == 0:
                    fallback_wuxing = ai_res.get("birth_element", "土")
                    suggest_list = local_fallback_name(sur, fallback_wuxing)
                render_bazi = {
                    "year": ai_res.get("year", ""),
                    "month": ai_res.get("month", ""),
                    "day": ai_res.get("day", ""),
                    "hour": ai_res.get("hour", ""),
                    "zodiac": pillar.get("zodiac", ""),
                    "birth_element": ai_res.get("birth_element", "土"),
                    "balance": ai_res.get("balance", "暂无八字分析"),
                    "full_analysis": ai_res.get("full_analysis", []),
                    "need_words": need_words,
                    "avoid_words": avoid_words,
                    "style_prefer": style_prefer
                }
                result = {
                    "input": {"surname": sur, "gender": gender, "birth": birth_str},
                    "bazi": render_bazi,
                    "time_period": pillar.get("time_period", ""),
                    "suggestions": suggest_list
                }
            except Exception as e:
                traceback.print_exc()
                error = "生成失败，请重新提交"
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

# 忘记密码重置页面路由
@app.route("/reset_pwd", methods=["GET", "POST"])
def reset_pwd_page():
    msg = ""
    msg_type = ""
    if request.method == "POST":
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

# ========== 注册蓝图 ==========
app.register_blueprint(api_bp, url_prefix="/api")

# 关键：host=0.0.0.0 局域网手机/平板全部可访问，实现多端共用数据库
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)