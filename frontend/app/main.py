# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# 导入拆分出去的路由
from app.web.views import router as web_router
from app.api.endpoints import router as api_router

app = FastAPI(title="MVP Demo")

##-----------------------##

#重要待办项
#app.event("startup")  # 启动路径配置未完成，如数据库连接

##-----------------------##

# 1. 自动计算路径
BASE_PATH = Path(__file__).resolve().parent.parent

# 2. 配置静态文件
app.mount("/static", StaticFiles(directory=str(BASE_PATH / "static")), name="static")

# 3. 包含路由
# 页面路由（不加前缀，直接访问 /）
app.include_router(web_router)

# API 路由（统一加上 /api 前缀，方便管理）
app.include_router(api_router, prefix="/api", tags=["数据接口"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True) #默认端口8000