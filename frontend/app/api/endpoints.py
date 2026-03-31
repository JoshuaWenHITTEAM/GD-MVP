# app/api/endpoints.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.models.schemas import AlgorithmRegister, AlgorithmResponse
from app.models.database import get_db, AlgorithmModel

# 创建 APIRouter 实例，用于分组管理路由（例如 web 相关的路由）
router = APIRouter()

@router.get("/test")
async def test_api():
    return {"status": "success", "message": "API 接口已连通"}

@router.post("/algorithm/register", response_model=AlgorithmResponse, tags=["算法管理"])
async def register_algorithm(
    algorithm: AlgorithmRegister,
    db: Session = Depends(get_db)
):
    """
    注册新算法
    - 算法名称：必填，最多 32 字符
    - 版本号：必填，语义化版本
    - 算法类型：必填，深度学习或机器学习
    - 标签：必填，任务类型
    - 描述：可选
    - 权限：公开/共享/私有
    """
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
    """获取所有已注册的算法列表"""
    algorithms = db.query(AlgorithmModel).order_by(AlgorithmModel.created_at.desc()).all()
    return algorithms

@router.get("/algorithm/{algorithm_id}", response_model=AlgorithmResponse, tags=["算法管理"])
async def get_algorithm(algorithm_id: int, db: Session = Depends(get_db)):
    """根据 ID 获取算法详情"""
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
    """
    搜索算法：
    - keyword：模糊匹配算法名称（name）或描述（description）
    - algorithm_type：精确匹配算法类型
    """
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