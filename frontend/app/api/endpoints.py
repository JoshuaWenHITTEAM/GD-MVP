# app/api/endpoints.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime
from app.models.schemas import AlgorithmRegister, AlgorithmResponse
from app.models.database import get_db, AlgorithmModel,AlgorithmVersionModel
from sse_starlette.sse import EventSourceResponse
import json
import asyncio
import uuid
import os
import shutil
from pathlib import Path
import httpx
from ..services.asset_service import asset_service
from typing import Optional
from frontend.app.services.job_service import job_service

# 创建 APIRouter 实例，用于分组管理路由（例如 web 相关的路由）
router = APIRouter()

@router.get("/test")
async def test_api():
    return {"status": "success", "message": "API 接口已连通"}

#========================================
#           p1部分接口(部分弃用)
#========================================
"""
@router.post("/algorithm/register", response_model=AlgorithmResponse, tags=["算法管理"])
async def register_algorithm(
    algorithm: AlgorithmRegister,
    db: Session = Depends(get_db)
):
    """"""
    注册新算法
    - 算法名称：必填，最多 32 字符
    - 版本号：必填，语义化版本
    - 算法类型：必填，深度学习或机器学习
    - 标签：必填，任务类型
    - 描述：可选
    - 权限：公开/共享/私有
    """"""
    # 检查同名算法是否已存在
    existing = db.query(AlgorithmModel).filter(
        AlgorithmModel.name == algorithm.name,
        AlgorithmModel.version == algorithm.version
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"算法 '{algorithm.name}' (版本：{algorithm.version}) 已存在"
        )
    
    # 创建新算法记录
    db_algorithm = AlgorithmModel(
        name=algorithm.name,
        version=algorithm.version,
        algorithm_type=algorithm.algorithm_type.value,
        tags=algorithm.tags,
        description=algorithm.description,
        auth=algorithm.auth.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(db_algorithm)
    db.commit()
    db.refresh(db_algorithm)
    
    return db_algorithm

@router.get("/algorithms", response_model=list[AlgorithmResponse], tags=["算法管理"])
async def list_algorithms(db: Session = Depends(get_db)):
    # 获取所有已注册的算法列表
    algorithms = db.query(AlgorithmModel).order_by(AlgorithmModel.created_at.desc()).all()
    return algorithms

@router.get("/algorithm/{algorithm_id}", response_model=AlgorithmResponse, tags=["算法管理"])
async def get_algorithm(algorithm_id: int, db: Session = Depends(get_db)):
    # 根据 ID 获取算法详情
    db_algorithm = db.query(AlgorithmModel).filter(AlgorithmModel.id == algorithm_id).first()
    if not db_algorithm:
        raise HTTPException(status_code=404, detail="算法未找到")
    return db_algorithm

# 删除算法（硬删除）
@router.delete("/algorithm/{algorithm_id}", tags=["算法管理"])
async def delete_algorithm(algorithm_id: int, db: Session = Depends(get_db)):
    db_algorithm = db.query(AlgorithmModel).filter(AlgorithmModel.id == algorithm_id).first()
    if not db_algorithm:
        raise HTTPException(status_code=404, detail="算法未找到")
    db.delete(db_algorithm)
    db.commit()
    return {"message": f"算法 '{db_algorithm.name}' 已删除"}


# 更新算法（可选，如果前端需要编辑功能）
@router.put("/algorithm/{algorithm_id}", response_model=AlgorithmResponse, tags=["算法管理"])
async def update_algorithm(
        algorithm_id: int,
        algorithm: AlgorithmRegister,
        db: Session = Depends(get_db)
):
    db_algorithm = db.query(AlgorithmModel).filter(AlgorithmModel.id == algorithm_id).first()
    if not db_algorithm:
        raise HTTPException(status_code=404, detail="算法未找到")

    # 检查名称+版本是否与其他记录冲突（排除自身）
    existing = db.query(AlgorithmModel).filter(
        AlgorithmModel.name == algorithm.name,
        AlgorithmModel.version == algorithm.version,
        AlgorithmModel.id != algorithm_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"算法 '{algorithm.name}' (版本：{algorithm.version}) 已存在"
        )

    db_algorithm.name = algorithm.name
    db_algorithm.version = algorithm.version
    db_algorithm.algorithm_type = algorithm.algorithm_type.value
    db_algorithm.tags = algorithm.tags
    db_algorithm.description = algorithm.description
    db_algorithm.auth = algorithm.auth.value
    db_algorithm.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_algorithm)
    return db_algorithm


# 搜索算法（支持关键词模糊搜索和类型筛选）
@router.get("/algorithms/search", response_model=list[AlgorithmResponse], tags=["算法管理"])
async def search_algorithms(
        keyword: str = None,  # 可选：搜索关键词（匹配名称或描述）
        algorithm_type: str = None,  # 可选：算法类型，如 "Deep Learning" 或 "Machine Learning"
        db: Session = Depends(get_db)
):
    """"""
    搜索算法：
    - keyword：模糊匹配算法名称（name）或描述（description）
    - algorithm_type：精确匹配算法类型
    """"""
    query = db.query(AlgorithmModel)

    # 关键词模糊搜索（不区分大小写，使用 ilike）
    if keyword:
        keyword_pattern = f"%{keyword}%"
        query = query.filter(
            (AlgorithmModel.name.ilike(keyword_pattern)) |
            (AlgorithmModel.description.ilike(keyword_pattern))
        )

    # 算法类型精确筛选（大小写敏感，因为数据库中存储的是 "Deep Learning"/"Machine Learning"）
    if algorithm_type:
        # 注意：前端传过来的值应该是 "Deep Learning" 或 "Machine Learning"
        query = query.filter(AlgorithmModel.algorithm_type == algorithm_type)

    # 按创建时间倒序
    results = query.order_by(AlgorithmModel.created_at.desc()).all()
    return results

# 上传目录
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# 接受镜像文件并对其进行校验
@router.post("/algorithm/upload-file/{algorithm_id}", tags=["算法管理"])
async def upload_algorithm_version(
    algorithm_id: int,
    file: UploadFile = File(...),
    rule: str = Form("json_schema"),  # 校验规则，可扩展
    version_number: str = Form(None),   # 前端可选传入版本号
    db: Session = Depends(get_db)
):
    """"""
    为指定算法上传文件并进行校验
    - algorithm_id: 算法ID
    - file: 上传的文件（.py, .json 等）
    - rule: 校验规则，例如 'json_schema', 'python_syntax' 等
    """"""
    # 1检查算法是否存在
    algorithm = db.query(AlgorithmModel).filter(AlgorithmModel.id == algorithm_id).first()
    if not algorithm:
        raise HTTPException(status_code=404, detail="算法不存在")

    # 读取文件内容
    contents = await file.read()
    file_extension = Path(file.filename).suffix.lower()

    # 根据规则校验
    validation_result = validate_file(contents, file_extension, rule)
    if not validation_result["valid"]:
        raise HTTPException(status_code=400, detail=validation_result["error"])

    # 生成版本号（如果前端未提供）
    if not version_number:
        # 获取该算法已有的最大版本号（简单递增数字）
        existing_versions = db.query(AlgorithmVersionModel).filter(
            AlgorithmVersionModel.algorithm_id == algorithm_id
        ).order_by(AlgorithmVersionModel.id.desc()).first()
        if existing_versions:
            # 尝试从版本号中提取数字，例如 v1.0.0 -> 1.0.0，然后自增小版本
            last_num = existing_versions.version_number
            # 简单处理：假设版本号格式为 vX.Y.Z，自动升级 Z
            import re
            match = re.match(r"v(\d+)\.(\d+)\.(\d+)", last_num)
            if match:
                major, minor, patch = map(int, match.groups())
                new_version = f"v{major}.{minor}.{patch + 1}"
            else:
                new_version = "v1.0.1"
        else:
            new_version = "v1.0.0"
        version_number = new_version

    # 保存文件到服务器
    safe_filename = f"{algorithm_id}_{version_number}_{file.filename}"
    file_path = UPLOAD_DIR / safe_filename
    with open(file_path, "wb") as f:
        f.write(contents)

        # 创建版本记录
    version_record = AlgorithmVersionModel(
        algorithm_id=algorithm_id,
        version_number=version_number,
        file_path=str(file_path),
        rule_used=rule,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(version_record)
    algorithm.file_path = str(file_path)
    algorithm.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(version_record)
    db.refresh(algorithm)
    return {
        "message": "版本上传成功",
        "version": version_record.version_number,
        "file_path": version_record.file_path,
        "algorithm_id": algorithm_id
    }

def validate_file(contents: bytes, extension: str, rule: str) -> dict:
    # 根据规则校验文件内容
    # if rule == "json_schema":
    #     # 示例：校验是否为合法JSON且包含必要字段
    #     try:
    #         import json
    #         data = json.loads(contents.decode('utf-8'))
    #         required_fields = ["model_name", "version", "input_shape"]
    #         missing = [f for f in required_fields if f not in data]
    #         if missing:
    #             return {"valid": False, "error": f"JSON缺少必要字段: {missing}"}
    #         return {"valid": True, "error": None}
    #     except Exception as e:
    #         return {"valid": False, "error": f"JSON解析失败: {str(e)}"}
    # elif rule == "python_syntax":
    #     # 校验Python语法
    #     try:
    #         compile(contents, '<string>', 'exec')
    #         return {"valid": True, "error": None}
    #     except SyntaxError as e:
    #         return {"valid": False, "error": f"Python语法错误: {str(e)}"}
    # else:
    #     # 默认只校验非空
    #     if len(contents) == 0:
    #         return {"valid": False, "error": "文件为空"}
    return {"valid": True, "error": None}


@router.get("/algorithm/{algorithm_id}/file-content", tags=["算法管理"])
async def get_algorithm_file_content(algorithm_id: int, db: Session = Depends(get_db)):
    # 获取算法当前关联的镜像文件内容
    algorithm = db.query(AlgorithmModel).filter(AlgorithmModel.id == algorithm_id).first()
    if not algorithm:
        raise HTTPException(status_code=404, detail="算法不存在")
    if not algorithm.file_path:
        raise HTTPException(status_code=404, detail="该算法尚未上传任何镜像文件")

    file_path = Path(algorithm.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件已丢失")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")

    return {
        "filename": file_path.name,
        "content": content,
        "algorithm_name": algorithm.name,
        "algorithm_version": algorithm.version
    }
"""
# 获取算法的所有历史版本列表
@router.get("/algorithm/{algorithm_id}/versions", tags=["算法管理"])
async def get_algorithm_versions(algorithm_id: int, db: Session = Depends(get_db)):
    """获取指定算法的所有历史版本（按创建时间倒序）"""
    algorithm = db.query(AlgorithmModel).filter(AlgorithmModel.id == algorithm_id).first()
    if not algorithm:
        raise HTTPException(status_code=404, detail="算法不存在")
    versions = db.query(AlgorithmVersionModel).filter(
        AlgorithmVersionModel.algorithm_id == algorithm_id
    ).order_by(AlgorithmVersionModel.created_at.desc()).all()
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "file_path": v.file_path,
            "rule_used": v.rule_used,
            "created_at": v.created_at.isoformat()
        }
        for v in versions
    ]


# 回滚到指定版本（直接更新当前算法指向的文件路径）
@router.post("/algorithm/{algorithm_id}/rollback/{version_id}", tags=["算法管理"])
async def rollback_to_version(algorithm_id: int, version_id: int, db: Session = Depends(get_db)):
    """将算法的当前文件回滚到指定的历史版本"""
    algorithm = db.query(AlgorithmModel).filter(AlgorithmModel.id == algorithm_id).first()
    if not algorithm:
        raise HTTPException(status_code=404, detail="算法不存在")
    target_version = db.query(AlgorithmVersionModel).filter(
        AlgorithmVersionModel.id == version_id,
        AlgorithmVersionModel.algorithm_id == algorithm_id
    ).first()
    if not target_version:
        raise HTTPException(status_code=404, detail="指定的版本不存在")

    # 更新算法的当前文件路径
    algorithm.file_path = target_version.file_path
    algorithm.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(algorithm)
    return {
        "message": f"已成功回滚到版本 {target_version.version_number}",
        "version": target_version.version_number,
        "file_path": target_version.file_path
    }

#==================================
#           p2部分接口
#==================================


@router.get("/v1/train/jobs")
async def get_jobs():
    return await job_service.get_history()

@router.post("/v1/train/jobs")
async def create_job(request: Request):
    data = await request.json()
    return await job_service.create_job(data['task_type'], data['config'])

@router.get("/v1/train/jobs/{job_id}")
async def get_job_detail(job_id: str):
    return await job_service.get_job_detail(job_id)

@router.post("/v1/train/jobs/{job_id}/stop")
async def stop_job(job_id: str):
    return await job_service.stop_job(job_id)

@router.get("/v1/train/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    # 直接代理后端的 SSE 流
    async def event_publisher():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", f"http://127.0.0.1:8000/api/train/jobs/{job_id}/stream") as resp:
                async for line in resp.aiter_lines():
                    if line:
                        yield line
    return EventSourceResponse(event_publisher())