from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateAlgorithmRequest(BaseModel):
    algorithmCode: str
    algorithmName: str
    algorithmType: str
    framework: str = ""
    runtimeType: str = ""
    languageType: str = ""
    codePath: str = ""
    configPath: str = ""
    description: str = ""


class CreateVersionRequest(BaseModel):
    version: str
    versionName: Optional[str] = None
    entrypoint: str
    sourceRevision: Optional[str] = None
    configRevision: Optional[str] = None
    changelog: str = ""
    sourceType: str = Field(default="local", description="镜像来源类型")
    localImageName: str = Field(default="", description="本地镜像名称")
    imagePullPolicy: str = Field(
        default="Never",
        description="镜像拉取策略",
    )
    registryUrl: str = Field(default="", description="镜像仓库地址")
    repositoryName: str = Field(default="", description="仓库名称")
    imageTag: str = Field(..., description="镜像标签")
    imageDigest: Optional[str] = Field(default=None, description="镜像摘要")
    fullImageUri: str = Field(default="", description="完整镜像地址")
    imageSize: Optional[int] = Field(default=None, description="镜像大小")


class UpdateAlgorithmRequest(BaseModel):
    algorithmCode: Optional[str] = None
    algorithmName: Optional[str] = None
    algorithmType: Optional[str] = None
    framework: Optional[str] = None
    runtimeType: Optional[str] = None
    languageType: Optional[str] = None
    codePath: Optional[str] = None
    configPath: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class UpdateVersionRequest(BaseModel):
    version: Optional[str] = None
    versionName: Optional[str] = None
    entrypoint: Optional[str] = None
    sourceRevision: Optional[str] = None
    configRevision: Optional[str] = None
    changelog: Optional[str] = None
    publishStatus: Optional[str] = Field(
        default=None,
        description="发布状态，仅支持 DRAFT/PUBLISHED/OFFLINE",
    )
    sourceType: Optional[str] = Field(default=None, description="镜像来源类型")
    localImageName: Optional[str] = Field(default=None, description="本地镜像名称")
    imagePullPolicy: Optional[str] = Field(
        default=None,
        description="镜像拉取策略",
    )
    registryUrl: Optional[str] = Field(default=None, description="镜像仓库地址")
    repositoryName: Optional[str] = Field(default=None, description="仓库名称")
    imageTag: Optional[str] = Field(default=None, description="镜像标签")
    imageDigest: Optional[str] = Field(default=None, description="镜像摘要")
    fullImageUri: Optional[str] = Field(default=None, description="完整镜像地址")
    imageSize: Optional[int] = Field(default=None, description="镜像大小")


class CreateBuildRecordRequest(BaseModel):
    baseVersionUuid: Optional[str] = None
    outputVersionUuid: Optional[str] = None
    buildStatus: str = "PENDING"
    operator: str = ""
    buildSource: Optional[str] = None
    sourceRevision: Optional[str] = None
    configRevision: Optional[str] = None
    imageTag: Optional[str] = None
    imageDigest: Optional[str] = None
    fullImageUri: Optional[str] = None
    buildLogPath: Optional[str] = None
    errorMessage: Optional[str] = None
    resultSummary: Optional[str] = None


class UpdateBuildRecordRequest(BaseModel):
    outputVersionUuid: Optional[str] = None
    buildStatus: Optional[str] = None
    operator: Optional[str] = None
    buildSource: Optional[str] = None
    sourceRevision: Optional[str] = None
    configRevision: Optional[str] = None
    imageTag: Optional[str] = None
    imageDigest: Optional[str] = None
    fullImageUri: Optional[str] = None
    buildLogPath: Optional[str] = None
    errorMessage: Optional[str] = None
    resultSummary: Optional[str] = None
    finishedAt: Optional[datetime] = None
