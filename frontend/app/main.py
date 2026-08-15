import sys
import os
from pathlib import Path



current_file = Path(__file__).resolve() 
frontend_path = current_file.parent.parent 
root_path = frontend_path.parent
if str(frontend_path) not in sys.path:
    sys.path.insert(0, str(frontend_path))
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 导入业务模块
from app.web.views import router as web_router
from app.api.endpoints import router as api_router
from app.models.database import init_db

app = FastAPI(title="MVP Demo")

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 启动时初始化数据库

@app.on_event("startup")
async def startup_event():
    init_db()

# 配置静态文件路径
BASE_PATH = frontend_path
app.mount("/static", StaticFiles(directory=str(BASE_PATH / "static")), name="static")

# 注册路由
app.include_router(web_router)
app.include_router(api_router, prefix="/api", tags=["数据接口"])

if __name__ == "__main__":
    import uvicorn
    # app路径frontend.app.main:app
    uvicorn.run("frontend.app.main:app", host="127.0.0.1", port=8002, reload=True)