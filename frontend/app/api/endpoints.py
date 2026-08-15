# app/api/endpoints.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, UploadFile, File, Form
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
# from app.models.schemas import AlgorithmRegister, AlgorithmResponse
# from app.models.database import get_db, AlgorithmModel,AlgorithmVersionModel
from ..models.schemas import InferenceRequest, InferenceResponse
from ..models.database import get_db, get_postgres_db, AlgorithmModel,AlgorithmVersionModel,MediaAsset
import contextlib
import json
import mimetypes
import asyncio
import uuid
import os
import shutil
from pathlib import Path
import httpx
from ..services.asset_service import asset_service
from typing import AsyncIterator, Optional
from app.services.job_service import job_service
from app.services.algorithm_inference_service import algorithm_inference_service

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
async def get_algorithm_versions(algorithm_id: str, db: Session = Depends(get_db)):
    """获取指定算法的所有历史版本（按创建时间倒序）"""
    algorithm = db.query(AlgorithmModel).filter(AlgorithmModel.uuid == algorithm_id).first()
    if not algorithm:
        raise HTTPException(status_code=404, detail="算法不存在")
    versions = db.query(AlgorithmVersionModel).filter(
        AlgorithmVersionModel.algorithmUuid == algorithm_id,
        AlgorithmVersionModel.is_deleted == False
    ).order_by(AlgorithmVersionModel.createdAt.desc()).all()
    return [
        {
            "id": v.uuid,
            "algorithmUuid": v.algorithmUuid,
            "version": v.version,
            "versionName": v.versionName,
            "entrypoint": v.entrypoint,
            "sourceRevision": v.sourceRevision,
            "configRevision": v.configRevision,
            "changelog": v.changelog,
            "sourceType": v.sourceType,
            "localImageName": v.localImageName,
            "imagePullPolicy": v.imagePullPolicy,
            "registryUrl": v.registryUrl,
            "repositoryName": v.repositoryName,
            "imageTag": v.imageTag,
            "imageDigest": v.imageDigest,
            "fullImageUri": v.fullImageUri,
            "imageSize": v.imageSize,
            "publishStatus": v.publishStatus,
            "createdAt": v.createdAt.isoformat() if v.createdAt else None,
            "updatedAt": v.updatedAt.isoformat() if v.updatedAt else None,
        }
        for v in versions
    ]


# 回滚到指定版本（更新当前算法指向的代码/配置路径）
@router.post("/algorithm/{algorithm_id}/rollback/{version_id}", tags=["算法管理"])
async def rollback_to_version(algorithm_id: str, version_id: str, db: Session = Depends(get_db)):
    """将算法回滚到指定的历史版本"""
    algorithm = db.query(AlgorithmModel).filter(AlgorithmModel.uuid == algorithm_id).first()
    if not algorithm:
        raise HTTPException(status_code=404, detail="算法不存在")
    target_version = db.query(AlgorithmVersionModel).filter(
        AlgorithmVersionModel.uuid == version_id,
        AlgorithmVersionModel.algorithmUuid == algorithm_id,
        AlgorithmVersionModel.is_deleted == False
    ).first()
    if not target_version:
        raise HTTPException(status_code=404, detail="指定的版本不存在")

    # 版本表不再保存 file_path，回滚时同步当前算法关联的代码/配置路径
    algorithm.codePath = target_version.sourceRevision or algorithm.codePath
    algorithm.configPath = target_version.configRevision or algorithm.configPath
    algorithm.updatedAt = datetime.utcnow()
    db.commit()
    db.refresh(algorithm)
    return {
        "message": f"已成功回滚到版本 {target_version.version}",
        "versionId": target_version.uuid,
        "version": target_version.version,
        "versionName": target_version.versionName,
        "codePath": algorithm.codePath,
        "configPath": algorithm.configPath,
        "updatedAt": algorithm.updatedAt.isoformat() if algorithm.updatedAt else None,
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
    # 按行转发上游 SSE，保留 event/data 结构与空行分隔，避免大块缓冲
    async def event_publisher():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", f"http://127.0.0.1:30000/api/train/jobs/{job_id}/stream") as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    yield f"{line}\n".encode("utf-8")

    return StreamingResponse(
        event_publisher(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/v1/reasoning/stream")
async def stream_reasoning(request: Request):
    payload = await request.body()

    async def stop_algorithm_chain():
        with contextlib.suppress(Exception):
            async with httpx.AsyncClient(timeout=5.0) as stop_client:
                await stop_client.post("http://127.0.0.1:8010/api/stop")

    async def event_publisher():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    "http://127.0.0.1:8010/api/stream",
                    content=payload,
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if await request.is_disconnected():
                            await stop_algorithm_chain()
                            break
                        yield f"{line}\n".encode("utf-8")
        except GeneratorExit:
            await stop_algorithm_chain()
            raise
        except Exception:
            if await request.is_disconnected():
                await stop_algorithm_chain()
                return
            raise
        finally:
            if await request.is_disconnected():
                await stop_algorithm_chain()

    return StreamingResponse(
        event_publisher(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/v1/reasoning/stop")
async def stop_reasoning():
    stop_url = "http://127.0.0.1:8010/api/stop"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(stop_url)
            resp.raise_for_status()
            try:
                return resp.json()
            except ValueError:
                return {
                    "status": "stopping",
                    "upstream_status": resp.status_code,
                    "upstream_body": resp.text,
                }
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"algorithm chain stop failed at {stop_url}: {type(exc).__name__}: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"reasoning stop failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/v1/reasoning/frame/{task_id}/latest")
async def latest_reasoning_frame(task_id: str):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"http://127.0.0.1:8010/api/frame/{task_id}/latest")
            resp.raise_for_status()
            media_type = resp.headers.get("content-type", "image/jpeg")
            headers = {"Cache-Control": "no-store"}
            frame_index = resp.headers.get("x-frame-index")
            if frame_index is not None:
                headers["X-Frame-Index"] = frame_index
            return Response(content=resp.content, media_type=media_type, headers=headers)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"reasoning frame proxy failed: {type(exc).__name__}: {exc}",
        ) from exc

#==================================
#           数据库部分接口
#==================================
# 创建资产路由器
assets_router = APIRouter(prefix="/assets", tags=["资产管理"])

@assets_router.post("/upload")
async def upload_asset(
    file: UploadFile = File(...),
    media_type: str = Form(...),
    dataset_name: Optional[str] = Form(None),
    split: Optional[str] = Form(None),
    sequence_name: Optional[str] = Form(None),
    modality: Optional[str] = Form(None),
    previewable: Optional[bool] = Form(None),
    db: Session = Depends(get_postgres_db)
):
    asset = asset_service.upload_asset(
        db, file, media_type, dataset_name,
        split=split, sequence_name=sequence_name,
        modality=modality, previewable=previewable
    )
    return asset_service.asset_to_dict(asset)

@assets_router.get("")
async def list_assets(
    media_type: Optional[str] = None,
    dataset_name: Optional[str] = None,
    split: Optional[str] = None,
    sequence_name: Optional[str] = None,
    modality: Optional[str] = None,
    pageNum: int = 1,
    pageSize: int = 20,
    db: Session = Depends(get_postgres_db)
):
    total, items = asset_service.list_assets(
        db, media_type, dataset_name, 'active', None,
        pageNum, pageSize, split=split,
        sequence_name=sequence_name, modality=modality
    )
    return {"total": total, "items": [asset_service.asset_to_dict(item) for item in items]}

@assets_router.get("/minio-prefix")
async def list_assets_from_minio_prefix(
    bucket_name: str,
    object_prefix: str,
    media_type: str = 'image',
    pageSize: int = 200,
    db: Session = Depends(get_postgres_db),
):
    items = asset_service.sync_assets_from_minio_prefix(
        db,
        bucket_name=bucket_name,
        object_prefix=object_prefix,
        media_type=media_type,
        page_size=pageSize,
    )
    return {"total": len(items), "items": [asset_service.asset_to_dict(item) for item in items]}

@assets_router.get("/minio-sequences")
async def list_sequences_from_minio_prefix(
    bucket_name: str,
    object_prefix: str,
):
    items = asset_service.list_sequence_prefixes(
        bucket_name=bucket_name,
        object_prefix=object_prefix,
    )
    return {"total": len(items), "items": items}

@assets_router.get("/{asset_uuid}")
async def get_asset(asset_uuid: str, db: Session = Depends(get_postgres_db)):
    import uuid
    asset = asset_service.get_asset_or_404(db, uuid.UUID(asset_uuid))
    return asset_service.asset_to_dict(asset)

@assets_router.delete("/{asset_uuid}")
async def delete_asset(asset_uuid: str, db: Session = Depends(get_postgres_db)):
    import uuid
    asset = asset_service.logical_delete(db, uuid.UUID(asset_uuid))
    return {"uuid": str(asset.uuid), "status": asset.status}

@assets_router.get("/{asset_uuid}/preview")
async def preview_asset(asset_uuid: str, db: Session = Depends(get_postgres_db)):
    asset = asset_service.get_asset_or_404(db, uuid.UUID(asset_uuid))
    if not asset.previewable:
        raise HTTPException(status_code=400, detail="Current asset is not previewable")
    if asset.media_type not in {"image", "video"}:
        raise HTTPException(status_code=400, detail="Preview only supports image and video")

    response = asset_service.minio_service.get_object_stream(asset.bucket_name, asset.object_key)
    media_type = asset.content_type or mimetypes.guess_type(asset.original_name or asset.object_key)[0] or "application/octet-stream"

    def stream_object():
        try:
            for chunk in response.stream(32 * 1024):
                yield chunk
        finally:
            response.close()
            response.release_conn()

    return StreamingResponse(stream_object(), media_type=media_type)

@assets_router.get("/{asset_uuid}/preview-url")
async def get_preview_url(asset_uuid: str, db: Session = Depends(get_postgres_db)):
    asset = asset_service.get_asset_or_404(db, uuid.UUID(asset_uuid))
    if not asset.previewable:
        raise HTTPException(status_code=400, detail="Current asset is not previewable")
    if asset.media_type not in {"image", "video"}:
        raise HTTPException(status_code=400, detail="Preview only supports image and video")
    url = f"/api/assets/{asset_uuid}/preview"
    return {"url": url, "expiresIn": 1800}

@assets_router.get("/{asset_uuid}/download")
async def download_asset_file(asset_uuid: str, db: Session = Depends(get_postgres_db)):
    asset = asset_service.get_asset_or_404(db, uuid.UUID(asset_uuid))
    response = asset_service.minio_service.get_object_stream(asset.bucket_name, asset.object_key)
    media_type = asset.content_type or mimetypes.guess_type(asset.original_name or asset.object_key)[0] or "application/octet-stream"

    def stream_object():
        try:
            for chunk in response.stream(32 * 1024):
                yield chunk
        finally:
            response.close()
            response.release_conn()

    headers = {"Content-Disposition": f'attachment; filename="{asset.original_name or asset.object_key}"'}
    return StreamingResponse(stream_object(), media_type=media_type, headers=headers)

@assets_router.get("/{asset_uuid}/download-url")
async def get_download_url(asset_uuid: str, db: Session = Depends(get_postgres_db)):
    asset_service.get_asset_or_404(db, uuid.UUID(asset_uuid))
    url = f"/api/assets/{asset_uuid}/download"
    return {"url": url, "expiresIn": 1800}

# 在原来的 router 中包含资产路由
router.include_router(assets_router)

# ==================================
# 视觉算法推理接口
# ==================================
@router.get("/v1/vision/algorithms", tags=["视觉推理"])
async def list_vision_algorithms(db: Session = Depends(get_db)):
    items = await algorithm_inference_service.list_vision_algorithms(db)
    return {"items": items, "total": len(items)}


@router.post("/v1/runtime/versions/{version_uuid}/start", tags=["视觉推理"])
async def start_runtime(version_uuid: str, db: Session = Depends(get_db)):
    data = await algorithm_inference_service.start_runtime_for_version(db, version_uuid)
    return {"success": True, "data": data}


@router.post("/v1/runtime/versions/{version_uuid}/stop", tags=["视觉推理"])
async def stop_runtime(version_uuid: str, db: Session = Depends(get_db)):
    data = await algorithm_inference_service.stop_runtime_for_version(db, version_uuid)
    return {"success": True, "data": data}


@router.get("/v1/runtime/versions/{version_uuid}/status", tags=["视觉推理"])
async def runtime_status(version_uuid: str, db: Session = Depends(get_db)):
    data = await algorithm_inference_service.get_runtime_status_for_version(db, version_uuid)
    return {"success": True, "data": data}


@router.post("/v1/vision/inference", response_model=InferenceResponse, tags=["视觉推理"])
async def vision_inference(
    request: InferenceRequest,
    db: Session = Depends(get_db),
    pg_db: Session = Depends(get_postgres_db),
):
    result = await algorithm_inference_service.run_inference(
        db=db,
        pg_db=pg_db,
        version_uuid=request.version_uuid,
        asset_uuid=request.asset_uuid,
        asset_uuids=request.asset_uuids,
        template_bbox=request.template_bbox,
    )
    return InferenceResponse(success=True, result=result, message="推理完成")


@router.post("/v1/vision/tracking-stream", tags=["视觉推理"])
async def vision_tracking_stream(
    request: InferenceRequest,
    db: Session = Depends(get_db),
    pg_db: Session = Depends(get_postgres_db),
):
    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in algorithm_inference_service.stream_tracking_inference(
                db=db,
                pg_db=pg_db,
                version_uuid=request.version_uuid,
                asset_uuids=request.asset_uuids,
                template_bbox=request.template_bbox,
            ):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except HTTPException as exc:
            yield json.dumps({
                "event": "error",
                "detail": exc.detail,
                "status_code": exc.status_code,
            }, ensure_ascii=False) + "\n"
        except Exception as exc:
            yield json.dumps({
                "event": "error",
                "detail": str(exc),
                "status_code": 500,
            }, ensure_ascii=False) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
