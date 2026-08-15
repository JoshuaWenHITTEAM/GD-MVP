from fastapi import APIRouter

from app.api.v1.algorithm import router as algorithm_router
from app.api.v1.assets import router as assets_router
from app.api.v1.results import router as results_router


api_router = APIRouter(prefix='/api/v1')
api_router.include_router(assets_router)
api_router.include_router(results_router)
api_router.include_router(algorithm_router)
