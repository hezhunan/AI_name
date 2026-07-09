一、环境依赖
Python 版本要求：Python 3.8 及以上版本
终端安装依赖命令：
    # 核心web框架
    pip install flask
    # 智谱AI官方SDK，用于调用大模型生成八字、姓名
    pip install zai-sdk
二、使用方式：
1.打开终端，进入项目根目录
2.执行启动命令：python app.py
3.服务启动成功后访问地址：
    本机访问：http://127.0.0.1:5000
    局域网手机 / 其他电脑访问：http://本机局域网IP:5000