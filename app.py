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
from datetime import datetime

app = Flask(__name__)
app.register_blueprint(api_bp, url_prefix="/api")

# ===================== 智谱SDK配置 =====================
ZHIPU_API_KEY = "00e172fcad8844afae3531c0123758eb.LWb2F0bsOK2IOd1n"
client = ZhipuAI(api_key=ZHIPU_API_KEY)

# ===================== 干支生肖计算工具（修复生肖固定马） =====================
TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
ZODIAC_MAP = {
    "子": "鼠", "丑": "牛", "寅": "虎", "卯": "兔",
    "辰": "龙", "巳": "蛇", "午": "马", "未": "羊",
    "申": "猴", "酉": "鸡", "戌": "狗", "亥": "猪"
}

def get_year_ganzhi_zodiac(year: int):
    base_year = 4
    offset = year - base_year
    gan_idx = offset % 10
    zhi_idx = offset % 12
    gan = TIAN_GAN[gan_idx]
    zhi = DI_ZHI[zhi_idx]
    zodiac = ZODIAC_MAP[zhi]
    return gan, zhi, zodiac

# 随机喜用神五行
def calc_random_five():
    return random.choice(["金", "木", "水", "火", "土"])

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

# 智谱大模型调用函数（增加编码容错，纯英文打印规避编码崩溃）
def glm_generate_name(surname, gender, birth, target_five):
    print("===== Start Zhipu GLM API Call =====")
    print(f"Params: surname={surname}, gender={gender}, birth={birth}, element={target_five}")

    system_prompt = "You are a professional Chinese naming master. Only output pure JSON array, no extra text, comments, line breaks."
    user_prompt = f"Surname {surname}, baby gender {gender}, birth date {birth}, favorable five element {target_five}. Generate 3 two-character names, return JSON array, each item has name, meaning, source_tags array."

    try:
        response = client.chat.completions.create(
            model="glm-5.2",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.6
        )
        model_content = response.choices[0].message.content
        print("Model raw output:", model_content)
        return json.loads(model_content)
    except Exception as e:
        print(f"Zhipu API Exception: {str(e)}")
        return local_fallback_name(surname, target_five)

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
        birth = request.form.get("birth")
        if not sur or not birth:
            error = "姓氏与出生时间不能为空"
        else:
            target_five = calc_random_five()
            suggestions = glm_generate_name(sur, gender, birth, target_five)
            birth_dt = datetime.strptime(birth, "%Y-%m-%dT%H:%M")
            birth_year = birth_dt.year
            year_gan, year_zhi, zodiac = get_year_ganzhi_zodiac(birth_year)
            year_zhu = year_gan + year_zhi
            hour_str = birth_dt.strftime("%H时")

            bazi_data = {
                "year": year_zhu,
                "month": "甲午",
                "day": "甲子",
                "hour": "丙寅",
                "zodiac": zodiac,
                "birth_element": target_five,
                "balance": f"日主喜用神为{target_five}，起名优先匹配对应五行汉字",
                "full_analysis": [
                    f"年柱{year_zhu}，主一生性格与早年格局",
                    "月柱甲午木火相生，聪慧灵动",
                    "日柱日主根基，本性善良正直",
                    "时柱利学业、晚年前程顺遂"
                ]
            }
            result = {
                "input": {"surname": sur, "gender": gender, "birth": birth},
                "bazi": bazi_data,
                "time_period": hour_str,
                "suggestions": suggestions
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
        birth = request.form.get("birth")
        if not sur or not birth:
            error = "姓氏与出生时间不能为空"
        else:
            target_five = calc_random_five()
            suggestions = glm_generate_name(sur, gender, birth, target_five)
            birth_dt = datetime.strptime(birth, "%Y-%m-%dT%H:%M")
            birth_year = birth_dt.year
            year_gan, year_zhi, zodiac = get_year_ganzhi_zodiac(birth_year)
            year_zhu = year_gan + year_zhi
            hour_str = birth_dt.strftime("%H时")

            bazi_data = {
                "year": year_zhu,
                "month": "甲午",
                "day": "甲子",
                "hour": "丙寅",
                "zodiac": zodiac,
                "birth_element": target_five,
                "balance": f"日主喜用神为{target_five}，起名优先匹配对应五行汉字",
                "full_analysis": [
                    f"年柱{year_zhu}，主一生性格与早年格局",
                    "月柱甲午木火相生，聪慧灵动",
                    "日柱日主根基，本性善良正直",
                    "时柱利学业、晚年前程顺遂"
                ]
            }
            result = {
                "input": {"surname": sur, "gender": gender, "birth": birth},
                "bazi": bazi_data,
                "time_period": hour_str,
                "suggestions": suggestions
            }
    return render_template("tourist.html", result=result, error=error)

@app.route("/user")
def user_center():
    return render_template("user.html")

if __name__ == "__main__":
    app.run(debug=True)