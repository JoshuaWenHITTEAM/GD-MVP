# app/api/endpoints.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
async def test_api():
    return {"status": "success", "message": "API 接口已连通"}

# @router.post("/train-model")
# @router.post("/do-reasoning")