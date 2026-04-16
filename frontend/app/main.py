# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.web.views import router as web_router
from app.api.endpoints import router as api_router
from app.models.database import init_db
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MVP Demo")

# 允许跨域
"""
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # MVP 阶段允许所有源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
"""

# 启动时初始化数据库
"""
@app.on_event("startup")
async def startup_event():
    init_db()
"""


# 1. 自动计算路径
BASE_PATH = Path(__file__).resolve().parent.parent

# 2. 配置静态文件
app.mount("/static", StaticFiles(directory=str(BASE_PATH / "static")), name="static")

# 3. 包含路由
# 页面路由（不加前缀，直接访问 /）
app.include_router(web_router)

# API 接口（统一加上 /api 前缀，方便管理）
app.include_router(api_router, prefix="/api", tags=["数据接口"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True) # 默认端口8000