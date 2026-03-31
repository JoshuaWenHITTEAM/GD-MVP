from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class AlgorithmType(str, Enum):
    DEEP_LEARNING = "Deep Learning"
    MACHINE_LEARNING = "Machine Learning"


class AlgorithmAuth(str, Enum):   # 算法权限
    PUBLIC = "公开"
    SHARED = "共享"
    PRIVATE = "私有"


class AlgorithmRegister(BaseModel):
    """算法注册请求模型"""
    """算法注册请求模型"""
    name: str = Field(..., max_length=32, description="算法名称")
    version: str = Field(..., description="版本号")
    algorithm_type: AlgorithmType = Field(..., description="算法类型")
    tags: str = Field(..., description="标签分类")
    description: Optional[str] = Field(None, description="算法描述")
    auth: AlgorithmAuth = Field(AlgorithmAuth.PUBLIC, description="算法权限")


class AlgorithmResponse(BaseModel):
    """算法注册响应模型"""
    id: int
    name: str
    version: str
    algorithm_type: str
    tags: str
    description: Optional[str]
    auth: str
    created_at: datetime

    class Config:
        from_attributes = True
