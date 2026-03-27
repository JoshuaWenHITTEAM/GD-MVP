from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CreateAlgorithmRequest(BaseModel):
    algorithmCode: str
    algorithmName: str
    algorithmType: str
    framework: str = ""
    runtimeType: str = ""
    languageType: str = ""
    description: str = ""


class CreateVersionRequest(BaseModel):
    version: str
    versionName: str | None = None
    entrypoint: str
    configPath: str = ""
    changelog: str = ""


class UpdateAlgorithmRequest(BaseModel):
    algorithmCode: str | None = None
    algorithmName: str | None = None
    algorithmType: str | None = None
    framework: str | None = None
    runtimeType: str | None = None
    languageType: str | None = None
    description: str | None = None
    status: str | None = None


class UpdateVersionRequest(BaseModel):
    version: str | None = None
    versionName: str | None = None
    entrypoint: str | None = None
    configPath: str | None = None
    changelog: str | None = None
    publishStatus: str | None = None


class CreateImageRequest(BaseModel):
    registryUrl: str = Field(..., description="镜像仓库地址")
    repositoryName: str = Field(..., description="仓库名称")
    imageTag: str = Field(..., description="镜像标签")
    imageDigest: str | None = Field(default=None, description="镜像摘要")
    fullImageUri: str = Field(..., description="完整镜像地址")
    imageSize: int | None = Field(default=None, description="镜像大小")


class DeploymentResources(BaseModel):
    cpu: str | None = None
    memory: str | None = None


class CreateDeploymentRequest(BaseModel):
    algorithmVersionUuid: str
    imageUuid: str
    namespace: str = "default"
    port: int
    replicas: int = 1
    env: dict[str, str] = Field(default_factory=dict)
    resources: DeploymentResources | None = None


class ScaleRequest(BaseModel):
    replicas: int


class CreateDebugSessionRequest(BaseModel):
    algorithmUuid: str
    baseVersionUuid: str
    sessionName: str
    namespace: str = "debug"


class HotUpdateRequest(BaseModel):
    toVersionUuid: str
    updateType: Literal["code", "image", "config"] = "code"
    operator: str = ""


class CreateContainerRequest(BaseModel):
    algorithmVersionUuid: str
    imageUuid: str
    name: str
    version: str | None = None
    image: str | None = None
    namespace: str = "default"
    port: int
    replicas: int
    env: dict[str, str] = Field(default_factory=dict)
    cpu: str | None = None
    memory: str | None = None
