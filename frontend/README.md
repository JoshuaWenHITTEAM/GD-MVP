# GD-MVP项目前端
**本项目前端基于FastAPI、jinja2和uvicorn**

**Python=3.10**

## 快速开始

#### 安装依赖

`pip install -r requirements.txt`

#### 启动服务器

`uvicorn app.main:app --reload`

访问127.0.0.1:8000<br>
默认端口8000，可在app/main.py中配置

#### 数据库连接

在app/models/database.py中配置

## 文件结构

├── app/ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; # 服务器端功能，如api和路由<br>
├──── api/<br>
├──── web/<br>
├──── models/<br>
├── static/ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; # 静态资源<br>
├──── css/<br>
├──── js/<br>
├── templates/ &nbsp;&nbsp;&nbsp; # html<br>
└── README.md