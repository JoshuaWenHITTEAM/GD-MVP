from __future__ import annotations

from datetime import datetime
from typing import Literal

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
    versionName: str | None = None
    entrypoint: str
    sourceRevision: str | None = None
    configRevision: str | None = None
    changelog: str = ""
    sourceType: Literal["registry", "local"] = Field(default="local", description="镜像来源类型")
    localImageName: str = Field(default="", description="本地镜像名称")
    imagePullPolicy: Literal["Never", "IfNotPresent", "Always"] = Field(
        default="Never",
        description="镜像拉取策略",
    )
    registryUrl: str = Field(default="", description="镜像仓库地址")
    repositoryName: str = Field(default="", description="仓库名称")
    imageTag: str = Field(..., description="镜像标签")
    imageDigest: str | None = Field(default=None, description="镜像摘要")
    fullImageUri: str = Field(default="", description="完整镜像地址")
    imageSize: int | None = Field(default=None, description="镜像大小")


class UpdateAlgorithmRequest(BaseModel):
    algorithmCode: str | None = None
    algorithmName: str | None = None
    algorithmType: str | None = None
    framework: str | None = None
    runtimeType: str | None = None
    languageType: str | None = None
    codePath: str | None = None
    configPath: str | None = None
    description: str | None = None
    status: str | None = None


class UpdateVersionRequest(BaseModel):
    version: str | None = None
    versionName: str | None = None
    entrypoint: str | None = None
    sourceRevision: str | None = None
    configRevision: str | None = None
    changelog: str | None = None
    publishStatus: Literal["DRAFT", "PUBLISHED", "OFFLINE"] | None = Field(
        default=None,
        description="发布状态，仅支持 DRAFT/PUBLISHED/OFFLINE",
    )
    sourceType: Literal["registry", "local"] | None = Field(default=None, description="镜像来源类型")
    localImageName: str | None = Field(default=None, description="本地镜像名称")
    imagePullPolicy: Literal["Never", "IfNotPresent", "Always"] | None = Field(
        default=None,
        description="镜像拉取策略",
    )
    registryUrl: str | None = Field(default=None, description="镜像仓库地址")
    repositoryName: str | None = Field(default=None, description="仓库名称")
    imageTag: str | None = Field(default=None, description="镜像标签")
    imageDigest: str | None = Field(default=None, description="镜像摘要")
    fullImageUri: str | None = Field(default=None, description="完整镜像地址")
    imageSize: int | None = Field(default=None, description="镜像大小")


class CreateBuildRecordRequest(BaseModel):
    baseVersionUuid: str | None = None
    outputVersionUuid: str | None = None
    buildStatus: Literal["PENDING", "RUNNING", "SUCCESS", "FAILED"] = "PENDING"
    operator: str = ""
    buildSource: str | None = None
    sourceRevision: str | None = None
    configRevision: str | None = None
    imageTag: str | None = None
    imageDigest: str | None = None
    fullImageUri: str | None = None
    buildLogPath: str | None = None
    errorMessage: str | None = None
    resultSummary: str | None = None


class UpdateBuildRecordRequest(BaseModel):
    outputVersionUuid: str | None = None
    buildStatus: Literal["PENDING", "RUNNING", "SUCCESS", "FAILED"] | None = None
    operator: str | None = None
    buildSource: str | None = None
    sourceRevision: str | None = None
    configRevision: str | None = None
    imageTag: str | None = None
    imageDigest: str | None = None
    fullImageUri: str | None = None
    buildLogPath: str | None = None
    errorMessage: str | None = None
    resultSummary: str | None = None
    finishedAt: datetime | None = None
