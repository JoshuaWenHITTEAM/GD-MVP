# app/web/views.py
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
# 注意return新版写法，可能报错
# 获取根目录下的 templates 文件夹
BASE_PATH = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_PATH / "templates"))

@router.get("/")
async def read_p1(request: Request):
    return templates.TemplateResponse(request, "p1_admin.html")

@router.get("/train")
async def read_p2(request: Request):
    return templates.TemplateResponse(request, "p2_train.html")

@router.get("/reasoning")
async def read_p3(request: Request):
    return templates.TemplateResponse(request, "p3_reasoning.html")