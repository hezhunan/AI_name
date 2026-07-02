# 解决Windows中文编码报错，放在文件最顶部
import sys
import os
sys.stdout.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"

from flask import Flask, render_template, request, jsonify, redirect
import random
import json
import db
from api import api_bp
from zhipuai import ZhipuAI
from datetime import datetime, date
import calendar

app = Flask(__name__)
app.register_blueprint(api_bp, url_prefix="/api")

# ===================== 智谱SDK配置 =====================
ZHIPU_API_KEY = "00e172fcad8844afae3531c0123758eb.LWb2F0bsOK2IOd1n"
client = ZhipuAI(api_key=ZHIPU_API_KEY)

# ===================== 1. 本地八字排盘核心算法（关键新增） =====================
# 天干地支基础表
TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
ZODIAC_MAP = {
    "子": "鼠", "丑": "牛", "寅": "虎", "卯": "兔",
    "辰": "龙", "巳": "蛇", "午": "马", "未": "羊",
    "申": "猴", "酉": "鸡", "戌": "狗", "亥": "猪"
}

# 节气交接日（2000-2030简化版，用于月柱划分）
SOLAR_TERM_DAY = {
    1: [4, 19],
    2: [3, 18],
    3: [5, 20],
    4: [4, 20],
    5: [5, 21],
    6: [5, 21],
    7: [7, 22],
    8: [7, 23],
    9: [7, 23],
    10: [8, 24],
    11: [7, 22],
    12: [6, 21],
}

# 时辰对照表 23-1子,1-3丑...13-15未
SHI_CHEN_MAP = [
    ("子", 23, 0), ("丑", 1, 2), ("寅", 3, 4), ("卯", 5, 6),
    ("辰", 7, 8), ("巳", 9, 10), ("午", 11, 12), ("未", 13, 14),
    ("申", 15, 16), ("酉", 17, 18), ("戌", 19, 20), ("亥", 21, 22)
]

def get_year_gz(year):
    """计算年柱干支"""
    base = 4
    idx = (year - base) % 60
    g = idx % 10
    z = idx % 12
    return TIAN_GAN[g] + DI_ZHI[z]

def get_month_gz(year, month, day):
    """计算月柱干支，按节气划分月令"""
    year_g = get_year_gz(year)[0]
    year_g_idx = TIAN_GAN.index(year_g)
    m_base = [2, 4, 6, 8, 0, 2, 4, 6, 8, 0, 2, 4]
    m_start_idx = m_base[year_g_idx]
    # 判断是否过当月第一个节气
    cut_day = SOLAR_TERM_DAY[month][0]
    if day >= cut_day:
        m_idx = m_start_idx + month - 1
    else:
        m_idx = m_start_idx + month - 2
    g = m_idx % 10
    z = (month - 1) % 12
    return TIAN_GAN[g] + DI_ZHI[z]

def get_day_gz(year, month, day):
    """精准日柱干支计算（2000-2030有效）"""
    base_date = date(2000, 1, 1)
    target = date(year, month, day)
    delta = (target - base_date).days
    base_gz = 16  # 2000-01-01 甲子(0)偏移16
    total = base_gz + delta
    g = total % 10
    z = total % 12
    return TIAN_GAN[g] + DI_ZHI[z]

def get_shichen_gz(year, month, day, hour):
    """时柱干支"""
    day_g = get_day_gz(year, month, day)[0]
    day_g_idx = TIAN_GAN.index(day_g)
    shi_base = [0, 2, 4, 6, 8, 0, 2, 4, 6, 8]
    shi_start = shi_base[day_g_idx]
    # 匹配时辰地支
    shi_zhi = ""
    for z_name, h1, h2 in SHI_CHEN_MAP:
        if h1 <= hour <= h2:
            shi_zhi = z_name
            break
    z_idx = DI_ZHI.index(shi_zhi)
    g_idx = (shi_start + z_idx) % 10
    return TIAN_GAN[g_idx] + shi_zhi, shi_zhi

def get_full_birth_pillar(dt: datetime):
    """输入datetime对象，返回完整四柱、生肖、时辰文字"""
    y = dt.year
    m = dt.month
    d = dt.day
    h = dt.hour
    year_zhu = get_year_gz(y)
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

# 本地兜底起名（API失败备用）
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

# 智谱大模型调用：仅传入固定四柱，只做喜用神分析+起名，不再排盘
def glm_analysis_name(surname, gender, pillar_info):
    print("===== Start Zhipu GLM API Call =====")
    print(f"Params: surname={surname}, gender={gender}, pillar={pillar_info}")

    system_prompt = """
你是专业传统八字命理起名大师，四柱八字已经由系统精准计算完毕，你只负责分析旺衰、确定唯一喜用神、生成全新不重复的名字。
硬性强制规则，必须严格遵守：
1. 给定四柱不可修改，只基于固定八字分析；
2. 根据八字旺衰得出唯一喜用神（金/木/水/火/土其中一个）；
3. 【最重要】每次调用必须生成**完全不同、从未出现过**的3个双字名字，禁止复用之前生成过的字词、组合；
4. 名字用字优先取自诗经、楚辞、唐诗宋词等古典典籍，提高独特性；
5. 男名大气开阔、格局宏大；女名温婉雅致、清新柔和；
6. 每个名字的寓意、典故、标签全部独立，不重复文案；
7. 输出仅纯净JSON，无任何多余文字、注释、换行、markdown；

JSON固定结构：
{
    "birth_element": "单一五行字（金/木/水/火/土）",
    "balance": "完整八字分析，说明日主旺衰、全局五行格局、为何取该喜用神，文案每次略有区分，不要完全复制上一次",
    "full_analysis": [
        "年柱单独解读（每次措辞微调，避免完全重复）",
        "月柱单独解读（每次措辞微调，避免完全重复）",
        "日柱日主解读（每次措辞微调，避免完全重复）",
        "时柱运势解读（每次措辞微调，避免完全重复）"
    ],
    "suggestions": [
        {
            "name": "全新双字全名，不可与过往重复",
            "meaning": "名字寓意，标注契合喜用神五行，附带诗词出处，文案独一无二",
            "source_tags": ["喜用神X","古典诗词","男/女宝优选"]
        }
    ]
}
约束：
- full_analysis 固定4条；suggestions固定3个名字；
- 严禁重复名字、重复寓意、重复标签描述；
- 绝对不允许修改传入的四柱干支，只做分析起名。
"""
    user_prompt = f"""
姓氏：{surname}
性别：{gender}（male=男，female=女）
已精准排盘四柱：
年柱：{pillar_info['year']}
月柱：{pillar_info['month']}
日柱：{pillar_info['day']}
时柱：{pillar_info['hour']}
本次必须生成全新、无重复的3个名字，不要使用任何之前生成过的组合，严格按要求输出纯JSON，不要任何额外说明文字。
"""
    try:
        response = client.chat.completions.create(
            model="glm-5.2",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7  # 提高温度，增强创意多样性，名字差异更大
        )
        model_content = response.choices[0].message.content.strip()
        print("Model raw output:", model_content)
        data = json.loads(model_content)
        # 校验五行合法性
        valid_five = ["金", "木", "水", "火", "土"]
        if data.get("birth_element") not in valid_five:
            raise Exception("模型返回五行不合法")
        # 补齐四柱数据（本地算出，覆盖AI输出防止篡改）
        data["year"] = pillar_info["year"]
        data["month"] = pillar_info["month"]
        data["day"] = pillar_info["day"]
        data["hour"] = pillar_info["hour"]
        return data
    except Exception as e:
        print(f"Zhipu API Exception: {str(e)}")
        # 兜底应急方案
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

# ===================== 页面路由 =====================
@app.route("/")
def root_redirect():
    return redirect("/login")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/register")
def register_page():
    return render_template("register.html")

# 登录用户主页 /index
@app.route("/index", methods=["GET", "POST"])
def index_page():
    result = None
    error = None
    if request.method == "POST":
        sur = request.form.get("surname", "").strip()
        gender = request.form.get("gender")
        birth_str = request.form.get("birth")
        if not sur or not birth_str:
            error = "姓氏与出生时间不能为空"
        else:
            # 1. 前端datetime-local格式：2026-07-02T13:53
            birth_dt = datetime.strptime(birth_str, "%Y-%m-%dT%H:%M")
            # 2. 本地精准计算四柱，固定不变
            pillar = get_full_birth_pillar(birth_dt)
            # 3. 传给AI分析喜用神、生成名字
            ai_res = glm_analysis_name(sur, gender, pillar)
            # 4. 组装渲染数据
            bazi_data = {
                "year": pillar["year"],
                "month": pillar["month"],
                "day": pillar["day"],
                "hour": pillar["hour"],
                "zodiac": pillar["zodiac"],
                "birth_element": ai_res["birth_element"],
                "balance": ai_res["balance"],
                "full_analysis": ai_res["full_analysis"]
            }
            result = {
                "input": {"surname": sur, "gender": gender, "birth": birth_str},
                "bazi": bazi_data,
                "time_period": pillar["time_period"],
                "suggestions": ai_res["suggestions"]
            }
    return render_template("index.html", result=result, error=error)

# 游客页面 /tourist
@app.route("/tourist", methods=["GET", "POST"])
def tourist_page():
    result = None
    error = None
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
            bazi_data = {
                "year": pillar["year"],
                "month": pillar["month"],
                "day": pillar["day"],
                "hour": pillar["hour"],
                "zodiac": pillar["zodiac"],
                "birth_element": ai_res["birth_element"],
                "balance": ai_res["balance"],
                "full_analysis": ai_res["full_analysis"]
            }
            result = {
                "input": {"surname": sur, "gender": gender, "birth": birth_str},
                "bazi": bazi_data,
                "time_period": pillar["time_period"],
                "suggestions": ai_res["suggestions"]
            }
    return render_template("tourist.html", result=result, error=error)

@app.route("/user")
def user_center():
    return render_template("user.html")

if __name__ == "__main__":
    app.run(debug=True)