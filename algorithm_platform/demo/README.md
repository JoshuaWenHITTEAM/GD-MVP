# Algorithm Platform Demo Backend

基于 FastAPI + MySQL 的算法平台后端 Demo。

当前版本的数据模型已经收敛为：

- 一个算法对应多个版本
- 一个版本就是一个可执行发布单元
- 版本本身同时携带外置代码、外置配置和镜像信息
- 一个部署只关联一个 `versionUuid`
- 为了支持溯源与回滚，额外保留 `build_records`

当前主流程是：

1. 创建算法
2. 创建算法版本
3. 构建新镜像并生成新版本
4. 记录构建过程到 `build_records`
5. 创建部署或把部署切换到新的 `versionUuid`

## 目录结构

- [app.py](/home/lurunda/GD-MVP/algorithm_platform/demo/app.py)
  API 入口与主要业务逻辑
- [db.py](/home/lurunda/GD-MVP/algorithm_platform/demo/db.py)
  MySQL 表结构、初始化与种子数据
- [models.py](/home/lurunda/GD-MVP/algorithm_platform/demo/models.py)
  请求模型定义
- [requirements.txt](/home/lurunda/GD-MVP/algorithm_platform/demo/requirements.txt)
  Python 依赖
- `runtime.py` 和 `scripts/` 目录仍保留在仓库中
- 但它们不再是当前主流程的一部分
- 当前主模型仅围绕 `algorithms / versions / deployments / build_records`

## 依赖

`requirements.txt` 当前内容：

- `fastapi>=0.110,<1.0`
- `uvicorn>=0.27,<1.0`
- `pydantic>=2.0,<3.0`
- `pymysql>=1.1,<2.0`

建议 Python 版本：

- Python 3.10+

安装依赖：

```bash
cd /home/lurunda/GD-MVP/algorithm_platform/demo
python3 -m pip install -r requirements.txt
```

默认 MySQL 连接参数与容器管理系统保持一致：

- `DEMO_DB_HOST=127.0.0.1`
- `DEMO_DB_PORT=3306`
- `DEMO_DB_USER=lurunda`
- `DEMO_DB_PASSWORD=G7v!Q2m#L9x@R4pZ`
- `DEMO_DB_NAME=algo_manager`

如需覆盖，可通过环境变量传入。

## 运行方式

开发模式启动：

```bash
cd /home/lurunda/GD-MVP/algorithm_platform/demo
python3 -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

启动后可访问：

- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## 数据库初始化

数据库定义位于：

- [db.py](/home/lurunda/GD-MVP/algorithm_platform/demo/db.py)

注意：

- 服务启动前需要保证 MySQL 服务可用
- 服务启动时会执行 `ensure_database()`
- 会自动创建数据库 `algo_manager`（或 `DEMO_DB_NAME` 指定的库）
- 当 `SCHEMA_VERSION` 变化时，仅会重建 demo 自己管理的表，不影响同库中的其他业务表
- schema 升级时 demo 数据会被清空并重新写入种子数据

当前 schema 版本：

- `2026-04-09-mysql`

## 数据库表结构与用途

### 1. `algorithms`

用途：

- 存储算法基础定义
- 一个算法可对应多个版本

主要字段：

- `uuid`
  算法主键
- `algorithmCode`
  算法编码，唯一
- `algorithmName`
  算法名称
- `algorithmType`
  算法类型
- `framework`
  框架
- `runtimeType`
  运行环境类型，如 CPU/GPU
- `languageType`
  开发语言
- `description`
  算法描述
- `status`
  算法状态
- `createdAt`
- `updatedAt`

### 2. `versions`

用途：

- 存储算法版本
- 版本是发布单元
- 版本同时承载：
  外置代码信息、外置配置信息、镜像信息

主要字段：

- `uuid`
  版本主键，外部统一使用 `versionUuid`
- `algorithmUuid`
  所属算法
- `version`
  版本号
- `versionName`
  版本名称
- `entrypoint`
  运行入口，例如 `python main.py`
- `codePath`
  外置代码目录
- `configPath`
  外置配置文件或配置目录路径
- `changelog`
  变更说明
- `sourceType`
  镜像来源，当前支持 `local` / `registry`
- `localImageName`
  本地镜像名
- `imagePullPolicy`
  镜像拉取策略
- `registryUrl`
  镜像仓库地址
- `repositoryName`
  仓库名称
- `imageTag`
  镜像标签
- `imageDigest`
  镜像摘要
- `fullImageUri`
  完整镜像地址
- `imageSize`
  镜像大小
- `publishStatus`
  发布状态
- `createdAt`
- `updatedAt`

说明：

- 原独立 `images` 表已经删除
- 现在“一个版本只对应一个镜像”
- 如果重新 build 新镜像，应创建新的版本
- `publishStatus` 当前采用状态机约束：
  `DRAFT -> PUBLISHED -> OFFLINE -> PUBLISHED`
- 允许同状态幂等更新
- 不允许直接 `DRAFT -> OFFLINE`
- 不允许回退到 `DRAFT`
- 如果版本仍有活跃部署，不允许从 `PUBLISHED` 切到 `OFFLINE`

### 3. `deployments`

用途：

- 存储部署实例
- 部署直接引用 `versionUuid`
- 当前运行镜像由版本解析得到

主要字段：

- `uuid`
  部署主键
- `versionUuid`
  当前部署使用的版本
- `namespace`
  命名空间
- `deploymentName`
  部署名
- `serviceName`
  服务名
- `status`
  部署状态
- `port`
  暴露端口
- `replicas`
  副本数
- `readyReplicas`
  就绪副本数
- `accessEndpoint`
  访问地址
- `errorMessage`
  错误信息
- `env`
  环境变量，JSON 字符串
- `resources`
  资源限制，JSON 字符串
- `image`
  实际使用的镜像地址
- `deployedAt`
- `updatedAt`

说明：

- 当 deployment 切换版本时，本质上就是把 `versionUuid` 指向新的版本
- 回滚也只是把 `versionUuid` 切回旧版本

### 4. `build_records`

用途：

- 存储构建记录
- 解决版本溯源、回滚依据和构建过程查询问题

主要字段：

- `uuid`
  构建记录主键
- `algorithmUuid`
  所属算法
- `baseVersionUuid`
  构建来源版本，可为空
- `outputVersionUuid`
  构建产出的版本，可为空
- `buildStatus`
  构建状态，例如 `PENDING` / `RUNNING` / `SUCCESS` / `FAILED`
- `operator`
  操作人
- `buildSource`
  构建来源说明，可为空
- `sourceRevision`
  源码版本标识，可为空
- `configRevision`
  配置版本标识，可为空
- `imageTag`
  本次构建产物的镜像标签，可为空
- `imageDigest`
  镜像摘要，可为空
- `fullImageUri`
  完整镜像地址，可为空
- `startedAt`
- `finishedAt`
- `buildLogPath`
  构建日志路径
- `errorMessage`
  错误信息
- `resultSummary`
  结果摘要

说明：

- `buildSource / sourceRevision / configRevision` 都是非必填
- 当前设计允许只记录核心构建结果，不强制记录源码或配置来源

## 当前 API 结构

### 算法

- `POST /api/v1/algorithms`
- `GET /api/v1/algorithms`
- `GET /api/v1/algorithms/{uuid}`
- `PUT /api/v1/algorithms/{uuid}`
- `DELETE /api/v1/algorithms/{uuid}`

### 版本

- `POST /api/v1/algorithms/{uuid}/versions`
- `GET /api/v1/algorithms/{uuid}/versions`
- `GET /api/v1/versions/{uuid}`
- `PUT /api/v1/versions/{uuid}`
- `DELETE /api/v1/versions/{uuid}`

说明：

- 创建版本时要直接提交镜像信息
- 不再有独立镜像接口
- 新建版本默认状态为 `DRAFT`
- 只有 `PUBLISHED` 状态的版本允许用于创建部署或切换部署
- 版本状态流转仅允许：
  `DRAFT -> PUBLISHED`、
  `PUBLISHED -> OFFLINE`、
  `OFFLINE -> PUBLISHED`

### 部署

- `POST /api/v1/deployments`
- `GET /api/v1/deployments`
- `GET /api/v1/deployments/{uuid}`
- `PUT /api/v1/deployments/{uuid}`
- `DELETE /api/v1/deployments/{uuid}`
- `POST /api/v1/deployments/{uuid}/restart`
- `POST /api/v1/deployments/{uuid}/scale`

说明：

- 创建部署时传 `versionUuid`
- 更新部署时可以切换到新的 `versionUuid`
- 创建部署和切换部署时，目标版本必须是 `PUBLISHED`
- 这就是当前模型里“发布切换/回滚”的核心动作

### 构建记录

- `POST /api/v1/algorithms/{uuid}/build-records`
- `GET /api/v1/algorithms/{uuid}/build-records`
- `GET /api/v1/build-records/{uuid}`
- `PUT /api/v1/build-records/{uuid}`
- `DELETE /api/v1/build-records/{uuid}`

说明：

- 构建系统可以先创建 `build_records`
- 构建完成后再更新状态、产物版本和镜像信息

## 种子数据

首次初始化后会自动写入一组 demo 数据：

- 算法 UUID: `alg-7f3d91b2-1f0f-4e1c-b123-001`
- 版本 UUID: `ver-b4e1b301-cb17-44f9-a001-101`
- 版本 UUID: `ver-a99d1c01-2f17-47f1-b001-102`

## 使用建议

- `codePath` 应指向后端机器上真实存在的代码目录
- `configPath` 应指向后端机器上真实存在的配置文件或配置目录
- 本地镜像场景建议：
  `sourceType=local`
  `localImageName=<本地镜像名>`
  `imagePullPolicy=Never`
- 当代码或配置变化并重新 build 出新镜像时：
  1. 创建新版本
  2. 记录构建过程到 `build_records`
  3. 将 deployment 切换到新的 `versionUuid`
- 回滚时不需要额外热更新表：
  直接把 deployment 切回旧的 `versionUuid` 即可
