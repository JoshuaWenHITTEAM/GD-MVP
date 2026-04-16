import re
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db import (
    DB_PATH,
    ensure_database,
    execute,import re
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db import (
    DB_PATH,
    ensure_database,
    execute,
    fetch_all,
    fetch_one,
    json_dumps,
    now_db,
    parse_deployment,
    to_db_datetime,
)
from models import (
    CreateAlgorithmRequest,
    CreateBuildRecordRequest,
    CreateDeploymentRequest,
    CreateVersionRequest,
    ScaleRequest,
    UpdateAlgorithmRequest,
    UpdateBuildRecordRequest,
    UpdateDeploymentRequest,
    UpdateVersionRequest,
)


app = FastAPI(
    title="光电感知系统 Demo Backend",
    version="0.6.0",
    description="按 Apifox 导出文档整理的 Python/FastAPI demo 后端，使用 MySQL 持久化存储",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_database()

ACTIVE_DEPLOYMENT_STATUSES = ("PENDING", "RUNNING", "UPDATING", "SCALING")
ACTIVE_DEPLOYMENT_SQL = ", ".join(f"'{status}'" for status in ACTIVE_DEPLOYMENT_STATUSES)
VERSION_PUBLISH_STATUSES = ("DRAFT", "PUBLISHED", "OFFLINE")
VERSION_PUBLISH_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"DRAFT", "PUBLISHED"},
    "PUBLISHED": {"PUBLISHED", "OFFLINE"},
    "OFFLINE": {"OFFLINE", "PUBLISHED"},
}


def gen_uuid(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def ok(data: Any) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "code": 0,
            "message": "success",
            "data": data,
        },
    )


def fail(code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "code": code,
            "message": message,
            "data": None,
        },
    )


class ApiError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@app.exception_handler(ApiError)
def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
    return fail(exc.code, exc.message)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or "demo"


def ensure(condition: bool, code: int, message: str) -> None:
    if not condition:
        raise ApiError(code, message)


def ensure_publish_status_transition(current_status: str, next_status: str) -> None:
    ensure(
        current_status in VERSION_PUBLISH_STATUSES,
        400,
        f"unsupported current publishStatus: {current_status}",
        )
    ensure(
        next_status in VERSION_PUBLISH_STATUSES,
        400,
        f"unsupported target publishStatus: {next_status}",
        )
    ensure(
        next_status in VERSION_PUBLISH_TRANSITIONS[current_status],
        400,
        (
            "invalid publishStatus transition: "
            f"{current_status} -> {next_status}; "
            "allowed transitions are DRAFT->PUBLISHED, PUBLISHED->OFFLINE, OFFLINE->PUBLISHED"
        ),
        )


def ensure_version_can_be_deployed(version: dict[str, Any]) -> None:
    ensure(
        version["publishStatus"] == "PUBLISHED",
        400,
        "only PUBLISHED versions can be deployed",
        )


def paginate(items: list[dict[str, Any]], page_num: int, page_size: int) -> dict[str, Any]:
    safe_page_num = max(page_num, 1)
    safe_page_size = max(page_size, 1)
    start = (safe_page_num - 1) * safe_page_size
    end = start + safe_page_size
    return {
        "items": items[start:end],
        "total": len(items),
        "pageNum": safe_page_num,
        "pageSize": safe_page_size,
    }


def algorithm_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "algorithmCode": item["algorithmCode"],
        "algorithmName": item["algorithmName"],
        "algorithmType": item["algorithmType"],
        "framework": item["framework"],
        "runtimeType": item["runtimeType"],
        "status": item["status"],
        "updatedAt": item["updatedAt"],
    }


def algorithm_detail(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "algorithmCode": item["algorithmCode"],
        "algorithmName": item["algorithmName"],
        "algorithmType": item["algorithmType"],
        "framework": item["framework"],
        "runtimeType": item["runtimeType"],
        "languageType": item["languageType"],
        "description": item["description"],
        "status": item["status"],
        "createdAt": item["createdAt"],
        "updatedAt": item["updatedAt"],
    }


def version_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "version": item["version"],
        "versionName": item["versionName"],
        "entrypoint": item["entrypoint"],
        "sourceType": item["sourceType"],
        "fullImageUri": item["fullImageUri"],
        "publishStatus": item["publishStatus"],
        "updatedAt": item["updatedAt"],
    }


def version_detail(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "algorithmUuid": item["algorithmUuid"],
        "version": item["version"],
        "versionName": item["versionName"],
        "entrypoint": item["entrypoint"],
        "codePath": item["codePath"],
        "configPath": item["configPath"],
        "changelog": item["changelog"],
        "sourceType": item["sourceType"],
        "localImageName": item["localImageName"],
        "imagePullPolicy": item["imagePullPolicy"],
        "registryUrl": item["registryUrl"],
        "repositoryName": item["repositoryName"],
        "imageTag": item["imageTag"],
        "imageDigest": item["imageDigest"],
        "fullImageUri": item["fullImageUri"],
        "imageSize": item["imageSize"],
        "publishStatus": item["publishStatus"],
        "createdAt": item["createdAt"],
        "updatedAt": item["updatedAt"],
    }

def deployment_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "versionUuid": item["versionUuid"],
        "namespace": item["namespace"],
        "deploymentName": item["deploymentName"],
        "serviceName": item["serviceName"],
        "status": item["status"],
        "image": item["image"],
        "accessEndpoint": item["accessEndpoint"],
        "replicas": item["replicas"],
        "readyReplicas": item["readyReplicas"],
        "port": item["port"],
        "is_deleted": item["is_deleted"],
        "updatedAt": item["updatedAt"],
    }


def deployment_detail(item: dict[str, Any]) -> dict[str, Any]:
    detail = deployment_summary(item)
    detail.update(
        {
            "errorMessage": item["errorMessage"],
            "deployedAt": item["deployedAt"],
        }
    )
    return detail


def build_record_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "algorithmUuid": item["algorithmUuid"],
        "baseVersionUuid": item["baseVersionUuid"],
        "outputVersionUuid": item["outputVersionUuid"],
        "buildStatus": item["buildStatus"],
        "operator": item["operator"],
        "startedAt": item["startedAt"],
        "finishedAt": item["finishedAt"],
    }


def build_record_detail(item: dict[str, Any]) -> dict[str, Any]:
    detail = build_record_summary(item)
    detail.update(
        {
            "buildSource": item["buildSource"],
            "sourceRevision": item["sourceRevision"],
            "configRevision": item["configRevision"],
            "imageTag": item["imageTag"],
            "imageDigest": item["imageDigest"],
            "fullImageUri": item["fullImageUri"],
            "buildLogPath": item["buildLogPath"],
            "errorMessage": item["errorMessage"],
            "resultSummary": item["resultSummary"],
        }
    )
    return detail


def deployment_endpoint(name: str, namespace: str, port: int) -> str:
    return f"http://{name}.{namespace}.svc.cluster.local:{port}"


def generate_unique_name(table: str, base: str, namespace: str) -> str:
    rows = fetch_all(
        """
        SELECT deploymentName
        FROM {}
        WHERE namespace = ? AND deploymentName LIKE ?
        """.format(table),
        (namespace, f"{base}%"),
    )
    used = {row["deploymentName"] for row in rows}
    index = 1
    candidate = f"{base}-{index}"
    while candidate in used:
        index += 1
        candidate = f"{base}-{index}"
    return candidate


def generate_deployment_name(algorithm_code: str, version: str, namespace: str) -> str:
    return generate_unique_name(
        "deployments",
        f"{slugify(algorithm_code)}-{slugify(version)}",
        namespace,
    )


def require_record(table: str, uuid: str, message: str) -> dict[str, Any]:
    item = fetch_one(f"SELECT * FROM {table} WHERE uuid = ?", (uuid,))
    ensure(item is not None, 404, message)
    return item  # type: ignore[return-value]


def require_algorithm(uuid: str) -> dict[str, Any]:
    return require_record("algorithms", uuid, "algorithm not found")


def require_version(uuid: str, message: str = "version not found") -> dict[str, Any]:
    return require_record("versions", uuid, message)


def require_build_record(uuid: str) -> dict[str, Any]:
    return require_record("build_records", uuid, "build record not found")


def require_deployment(uuid: str, message: str = "deployment not found") -> dict[str, Any]:
    item = fetch_one(
        "SELECT * FROM deployments WHERE uuid = ? AND is_deleted = 0",
        (uuid,),
    )
    ensure(item is not None, 404, message)
    return item  # type: ignore[return-value]


def touch_algorithm(uuid: str, updated_at: Any | None = None) -> None:
    execute(
        "UPDATE algorithms SET updatedAt = ? WHERE uuid = ?",
        (updated_at or now_db(), uuid),
    )


def touch_version(uuid: str, updated_at: Any | None = None) -> None:
    execute(
        "UPDATE versions SET updatedAt = ? WHERE uuid = ?",
        (updated_at or now_db(), uuid),
    )


def has_active_deployment(where_clause: str, params: tuple[Any, ...]) -> bool:
    row = fetch_one(
        f"""
        SELECT uuid
        FROM deployments
        WHERE is_deleted = 0 AND {where_clause} AND status IN ({ACTIVE_DEPLOYMENT_SQL})
        LIMIT 1
        """,
        params,
    )
    return row is not None


def resolve_version_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload["sourceType"] == "local":
        local_image_name = (payload.get("localImageName") or payload.get("fullImageUri") or "").strip()
        ensure(bool(local_image_name), 400, "localImageName is required for local images")
        if not payload.get("fullImageUri"):
            payload["fullImageUri"] = local_image_name
        payload["localImageName"] = local_image_name
        payload["imagePullPolicy"] = payload.get("imagePullPolicy") or "Never"
        payload["registryUrl"] = payload.get("registryUrl") or ""
        payload["repositoryName"] = payload.get("repositoryName") or ""
    else:
        ensure(bool(payload.get("fullImageUri")), 400, "fullImageUri is required for registry images")
        payload["localImageName"] = payload.get("localImageName") or ""
    return payload


def version_image_ref(version: dict[str, Any]) -> str:
    image_ref = (version.get("fullImageUri") or version.get("localImageName") or "").strip()
    ensure(bool(image_ref), 400, "version image is not configured")
    return image_ref


@app.post("/api/v1/algorithms")
def create_algorithm(body: CreateAlgorithmRequest):
    existing = fetch_one(
        "SELECT uuid FROM algorithms WHERE algorithmCode = ?",
        (body.algorithmCode,),
    )
    if existing:
        return fail(400, "algorithmCode already exists")

    algorithm_uuid = gen_uuid("alg")
    created_at = now_db()
    execute(
        """
        INSERT INTO algorithms (
            uuid, algorithmCode, algorithmName, algorithmType, framework,
            runtimeType, languageType, description, status, createdAt, updatedAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            algorithm_uuid,
            body.algorithmCode,
            body.algorithmName,
            body.algorithmType,
            body.framework or "",
            body.runtimeType or "",
            body.languageType or "",
            body.description or "",
            "ENABLED",
            created_at,
            created_at,
        ),
    )

    return ok(algorithm_detail(require_algorithm(algorithm_uuid)))


@app.get("/api/v1/algorithms")
def list_algorithms(
        keyword: str | None = Query(default=None),
        algorithmType: str | None = Query(default=None),
        pageNum: int = Query(default=1),
        pageSize: int = Query(default=10),
):
    rows = fetch_all("SELECT * FROM algorithms ORDER BY updatedAt DESC")
    items: list[dict[str, Any]] = []
    needle = keyword.lower() if keyword else None

    for item in rows:
        if algorithmType and item["algorithmType"] != algorithmType:
            continue
        if needle:
            haystack = " ".join(
                [item["algorithmCode"], item["algorithmName"], item["description"]]
            ).lower()
            if needle not in haystack:
                continue
        items.append(algorithm_summary(item))

    return ok(paginate(items, pageNum, pageSize))


@app.get("/api/v1/algorithms/{uuid}")
def get_algorithm(uuid: str):
    item = fetch_one("SELECT * FROM algorithms WHERE uuid = ?", (uuid,))
    if not item:
        return fail(404, "algorithm not found")
    return ok(algorithm_detail(item))


@app.put("/api/v1/algorithms/{uuid}")
def update_algorithm(uuid: str, body: UpdateAlgorithmRequest):
    item = fetch_one("SELECT * FROM algorithms WHERE uuid = ?", (uuid,))
    if not item:
        return fail(404, "algorithm not found")

    payload = body.model_dump(exclude_none=True)
    if "algorithmCode" in payload:
        existing = fetch_one(
            "SELECT uuid FROM algorithms WHERE algorithmCode = ? AND uuid != ?",
            (payload["algorithmCode"], uuid),
        )
        if existing:
            return fail(400, "algorithmCode already exists")

    if not payload:
        return ok(algorithm_detail(item))

    fields = []
    params: list[Any] = []
    for key, value in payload.items():
        fields.append(f"{key} = ?")
        params.append(value)
    fields.append("updatedAt = ?")
    params.append(now_db())
    params.append(uuid)

    execute(
        f"UPDATE algorithms SET {', '.join(fields)} WHERE uuid = ?",
        tuple(params),
    )
    updated = fetch_one("SELECT * FROM algorithms WHERE uuid = ?", (uuid,))
    return ok(algorithm_detail(updated))


@app.delete("/api/v1/algorithms/{uuid}")
def delete_algorithm(uuid: str):
    require_algorithm(uuid)
    active_deployment = fetch_one(
        """
        SELECT d.uuid
        FROM deployments d
        JOIN versions v ON v.uuid = d.versionUuid
        WHERE v.algorithmUuid = ? AND d.is_deleted = 0 AND d.status IN ({})
        LIMIT 1
        """.format(ACTIVE_DEPLOYMENT_SQL),
        (uuid,),
    )
    ensure(active_deployment is None, 400, "algorithm has active deployments")
    execute("DELETE FROM algorithms WHERE uuid = ?", (uuid,))
    return ok({"uuid": uuid})


@app.post("/api/v1/algorithms/{uuid}/versions")
def create_version(uuid: str, body: CreateVersionRequest):
    require_algorithm(uuid)
    payload = resolve_version_payload(body.model_dump())

    existing = fetch_one(
        "SELECT uuid FROM versions WHERE algorithmUuid = ? AND version = ?",
        (uuid, payload["version"]),
    )
    ensure(existing is None, 400, "version already exists under current algorithm")

    version_uuid = gen_uuid("ver")
    created_at = now_db()
    execute(
        """
        INSERT INTO versions (
            uuid, algorithmUuid, version, versionName, entrypoint,
            codePath, configPath, changelog, sourceType, localImageName,
            imagePullPolicy, registryUrl, repositoryName, imageTag,
            imageDigest, fullImageUri, imageSize, publishStatus, createdAt, updatedAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version_uuid,
            uuid,
            payload["version"],
            payload["versionName"] or payload["version"],
            payload["entrypoint"],
            payload["codePath"],
            payload["configPath"],
            payload["changelog"],
            payload["sourceType"],
            payload["localImageName"],
            payload["imagePullPolicy"],
            payload["registryUrl"],
            payload["repositoryName"],
            payload["imageTag"],
            payload["imageDigest"],
            payload["fullImageUri"],
            payload["imageSize"],
            "DRAFT",
            created_at,
            created_at,
        ),
    )
    touch_algorithm(uuid, created_at)

    return ok(version_detail(require_version(version_uuid)))


@app.get("/api/v1/algorithms/{uuid}/versions")
def list_versions(uuid: str):
    require_algorithm(uuid)
    rows = fetch_all(
        "SELECT * FROM versions WHERE algorithmUuid = ? ORDER BY updatedAt DESC",
        (uuid,),
    )
    items = [version_summary(item) for item in rows]
    return ok({"items": items, "total": len(items)})


@app.get("/api/v1/versions/{uuid}")
def get_version(uuid: str):
    return ok(version_detail(require_version(uuid)))


@app.put("/api/v1/versions/{uuid}")
def update_version(uuid: str, body: UpdateVersionRequest):
    item = require_version(uuid)

    payload = body.model_dump(exclude_none=True)
    if "publishStatus" in payload:
        ensure_publish_status_transition(item["publishStatus"], payload["publishStatus"])
        if item["publishStatus"] == "PUBLISHED" and payload["publishStatus"] == "OFFLINE":
            ensure(
                not has_active_deployment("versionUuid = ?", (uuid,)),
                400,
                "cannot offline version with active deployments",
            )
    merged_payload = dict(item)
    merged_payload.update(payload)
    merged_payload = resolve_version_payload(merged_payload)
    for key in (
            "sourceType",
            "localImageName",
            "imagePullPolicy",
            "registryUrl",
            "repositoryName",
            "imageTag",
            "imageDigest",
            "fullImageUri",
            "imageSize",
    ):
        payload[key] = merged_payload[key]
    if "version" in payload:
        existing = fetch_one(
            """
            SELECT uuid
            FROM versions
            WHERE algorithmUuid = ? AND version = ? AND uuid != ?
            """,
            (item["algorithmUuid"], payload["version"], uuid),
        )
        ensure(existing is None, 400, "version already exists under current algorithm")

    if not payload:
        return ok(version_detail(item))

    fields = []
    params: list[Any] = []
    for key, value in payload.items():
        fields.append(f"{key} = ?")
        params.append(value)
    fields.append("updatedAt = ?")
    updated_at = now_db()
    params.append(updated_at)
    params.append(uuid)

    execute(
        f"UPDATE versions SET {', '.join(fields)} WHERE uuid = ?",
        tuple(params),
    )
    touch_algorithm(item["algorithmUuid"], updated_at)
    return ok(version_detail(require_version(uuid)))


@app.delete("/api/v1/versions/{uuid}")
def delete_version(uuid: str):
    item = require_version(uuid)
    ensure(
        not has_active_deployment("versionUuid = ?", (uuid,)),
        400,
        "version has active deployments",
    )
    execute("DELETE FROM versions WHERE uuid = ?", (uuid,))
    touch_algorithm(item["algorithmUuid"])
    return ok({"uuid": uuid})


@app.post("/api/v1/deployments")
def create_deployment(body: CreateDeploymentRequest):
    version = require_version(body.versionUuid)
    ensure_version_can_be_deployed(version)
    algorithm = require_algorithm(version["algorithmUuid"])
    namespace = body.namespace
    deployment_name = generate_deployment_name(
        algorithm["algorithmCode"], version["version"], namespace
    )
    created_at = now_db()
    replicas = max(body.replicas, 1)
    resources = {}
    if body.resources:
        if body.resources.cpu is not None:
            resources["cpu"] = body.resources.cpu
        if body.resources.memory is not None:
            resources["memory"] = body.resources.memory

    item = {
        "uuid": gen_uuid("dep"),
        "versionUuid": body.versionUuid,
        "namespace": namespace,
        "deploymentName": deployment_name,
        "serviceName": f"{deployment_name}-svc",
        "status": "RUNNING",
        "image": version_image_ref(version),
        "port": body.port,
        "replicas": replicas,
        "readyReplicas": replicas,
        "accessEndpoint": deployment_endpoint(deployment_name, namespace, body.port),
        "errorMessage": "",
        "env": body.env,
        "resources": resources,
        "is_deleted": 0,
        "deployedAt": created_at,
        "updatedAt": created_at,
    }
    execute(
        """
        INSERT INTO deployments (
            uuid, versionUuid, namespace, deploymentName, serviceName,
            status, port, replicas, readyReplicas, accessEndpoint,
            errorMessage, env, resources, image, is_deleted, deployedAt, updatedAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item["uuid"],
            item["versionUuid"],
            item["namespace"],
            item["deploymentName"],
            item["serviceName"],
            item["status"],
            item["port"],
            item["replicas"],
            item["readyReplicas"],
            item["accessEndpoint"],
            item["errorMessage"],
            json_dumps(item["env"]),
            json_dumps(item["resources"]),
            item["image"],
            item["is_deleted"],
            item["deployedAt"],
            item["updatedAt"],
        ),
    )

    return ok(item)


@app.get("/api/v1/deployments")
def list_deployments(
        versionUuid: str | None = Query(default=None),
        namespace: str | None = Query(default=None),
        status: str | None = Query(default=None),
        pageNum: int = Query(default=1),
        pageSize: int = Query(default=10),
):
    rows = fetch_all(
        "SELECT * FROM deployments WHERE is_deleted = 0 ORDER BY updatedAt DESC"
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        item = parse_deployment(row)
        if versionUuid and item["versionUuid"] != versionUuid:
            continue
        if namespace and item["namespace"] != namespace:
            continue
        if status and item["status"] != status:
            continue
        items.append(deployment_summary(item))

    return ok(paginate(items, pageNum, pageSize))


@app.get("/api/v1/deployments/{uuid}")
def get_deployment(uuid: str):
    return ok(deployment_detail(parse_deployment(require_deployment(uuid))))


@app.put("/api/v1/deployments/{uuid}")
def update_deployment(uuid: str, body: UpdateDeploymentRequest):
    row = parse_deployment(require_deployment(uuid))
    payload = body.model_dump(exclude_none=True)
    if not payload:
        return ok(deployment_detail(row))

    next_version_uuid = payload.get("versionUuid", row["versionUuid"])
    next_version = require_version(next_version_uuid, "version not found")
    ensure_version_can_be_deployed(next_version)
    current_version = require_version(row["versionUuid"], "current version not found")
    ensure(
        next_version["algorithmUuid"] == current_version["algorithmUuid"],
        400,
        "target version does not belong to current algorithm",
        )

    next_port = payload.get("port", row["port"])
    next_env = payload.get("env", row["env"])
    next_resources = payload.get("resources", row["resources"])
    if hasattr(next_resources, "model_dump"):
        next_resources = next_resources.model_dump(exclude_none=True)

    execute(
        """
        UPDATE deployments
        SET versionUuid = ?, image = ?, port = ?, accessEndpoint = ?, env = ?, resources = ?, status = ?, updatedAt = ?
        WHERE uuid = ?
        """,
        (
            next_version_uuid,
            version_image_ref(next_version),
            next_port,
            deployment_endpoint(row["deploymentName"], row["namespace"], next_port),
            json_dumps(next_env),
            json_dumps(next_resources),
            "UPDATING",
            now_db(),
            uuid,
        ),
    )
    return ok(deployment_detail(parse_deployment(require_deployment(uuid))))


@app.delete("/api/v1/deployments/{uuid}")
def delete_deployment(uuid: str):
    require_deployment(uuid)
    updated_at = now_db()
    execute(
        """
        UPDATE deployments
        SET status = ?, readyReplicas = ?, is_deleted = ?, updatedAt = ?
        WHERE uuid = ?
        """,
        ("DELETED", 0, 1, updated_at, uuid),
    )
    return ok({"uuid": uuid, "status": "DELETED", "is_deleted": 1})


@app.post("/api/v1/deployments/{uuid}/restart")
def restart_deployment(uuid: str):
    row = require_deployment(uuid)
    ensure(row["status"] != "DELETED", 400, "deployment is deleted")

    execute(
        "UPDATE deployments SET status = ?, updatedAt = ? WHERE uuid = ?",
        ("UPDATING", now_db(), uuid),
    )
    return ok({"uuid": uuid, "status": "UPDATING"})


@app.post("/api/v1/deployments/{uuid}/scale")
def scale_deployment(uuid: str, body: ScaleRequest):
    row = require_deployment(uuid)
    ensure(body.replicas > 0, 400, "replicas must be greater than 0")

    execute(
        """
        UPDATE deployments
        SET status = ?, replicas = ?, readyReplicas = ?, updatedAt = ?
        WHERE uuid = ?
        """,
        ("SCALING", body.replicas, body.replicas, now_db(), uuid),
    )
    return ok(
        {
            "uuid": uuid,
            "namespace": row["namespace"],
            "deploymentName": row["deploymentName"],
            "status": "SCALING",
            "replicas": body.replicas,
        }
    )


@app.post("/api/v1/algorithms/{uuid}/build-records")
def create_build_record(uuid: str, body: CreateBuildRecordRequest):
    require_algorithm(uuid)
    if body.baseVersionUuid:
        base_version = require_version(body.baseVersionUuid, "base version not found")
        ensure(base_version["algorithmUuid"] == uuid, 400, "base version does not belong to current algorithm")
    if body.outputVersionUuid:
        output_version = require_version(body.outputVersionUuid, "output version not found")
        ensure(output_version["algorithmUuid"] == uuid, 400, "output version does not belong to current algorithm")

    started_at = now_db()
    finished_at = started_at if body.buildStatus in {"SUCCESS", "FAILED"} else None
    record_uuid = gen_uuid("bld")
    execute(
        """
        INSERT INTO build_records (
            uuid, algorithmUuid, baseVersionUuid, outputVersionUuid,
            buildStatus, operator, buildSource, sourceRevision, configRevision,
            imageTag, imageDigest, fullImageUri, startedAt, finishedAt,
            buildLogPath, errorMessage, resultSummary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_uuid,
            uuid,
            body.baseVersionUuid,
            body.outputVersionUuid,
            body.buildStatus,
            body.operator or "",
            body.buildSource,
            body.sourceRevision,
            body.configRevision,
            body.imageTag,
            body.imageDigest,
            body.fullImageUri,
            started_at,
            finished_at,
            body.buildLogPath or "",
            body.errorMessage or "",
            body.resultSummary or "",
        ),
    )
    return ok(build_record_detail(require_build_record(record_uuid)))


@app.get("/api/v1/algorithms/{uuid}/build-records")
def list_build_records(
        uuid: str,
        buildStatus: str | None = Query(default=None),
        pageNum: int = Query(default=1),
        pageSize: int = Query(default=10),
):
    require_algorithm(uuid)
    rows = fetch_all(
        "SELECT * FROM build_records WHERE algorithmUuid = ? ORDER BY startedAt DESC",
        (uuid,),
    )
    items: list[dict[str, Any]] = []
    for item in rows:
        if buildStatus and item["buildStatus"] != buildStatus:
            continue
        items.append(build_record_summary(item))
    return ok(paginate(items, pageNum, pageSize))


@app.get("/api/v1/build-records/{uuid}")
def get_build_record(uuid: str):
    return ok(build_record_detail(require_build_record(uuid)))


@app.put("/api/v1/build-records/{uuid}")
def update_build_record(uuid: str, body: UpdateBuildRecordRequest):
    item = require_build_record(uuid)
    payload = body.model_dump(exclude_none=True)
    if "outputVersionUuid" in payload:
        output_version = require_version(payload["outputVersionUuid"], "output version not found")
        ensure(output_version["algorithmUuid"] == item["algorithmUuid"], 400, "output version does not belong to current algorithm")
    if not payload:
        return ok(build_record_detail(item))
    if payload.get("buildStatus") in {"SUCCESS", "FAILED"} and "finishedAt" not in payload:
        payload["finishedAt"] = now_db()
    elif "finishedAt" in payload:
        payload["finishedAt"] = to_db_datetime(payload["finishedAt"])

    fields = []
    params: list[Any] = []
    for key, value in payload.items():
        fields.append(f"{key} = ?")
        params.append(value)
    params.append(uuid)
    execute(
        f"UPDATE build_records SET {', '.join(fields)} WHERE uuid = ?",
        tuple(params),
    )
    return ok(build_record_detail(require_build_record(uuid)))


@app.delete("/api/v1/build-records/{uuid}")
def delete_build_record(uuid: str):
    require_build_record(uuid)
    execute("DELETE FROM build_records WHERE uuid = ?", (uuid,))
    return ok({"uuid": uuid})


@app.get("/health")
def health():
    return {"status": "ok", "database": str(DB_PATH)}

    fetch_all,
    fetch_one,
    json_dumps,
    now_db,
    parse_deployment,
    to_db_datetime,
)
from models import (
    CreateAlgorithmRequest,
    CreateBuildRecordRequest,
    CreateDeploymentRequest,
    CreateVersionRequest,
    ScaleRequest,
    UpdateAlgorithmRequest,
    UpdateBuildRecordRequest,
    UpdateDeploymentRequest,
    UpdateVersionRequest,
)


app = FastAPI(
    title="光电感知系统 Demo Backend",
    version="0.6.0",
    description="按 Apifox 导出文档整理的 Python/FastAPI demo 后端，使用 MySQL 持久化存储",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_database()

ACTIVE_DEPLOYMENT_STATUSES = ("PENDING", "RUNNING", "UPDATING", "SCALING")
ACTIVE_DEPLOYMENT_SQL = ", ".join(f"'{status}'" for status in ACTIVE_DEPLOYMENT_STATUSES)
VERSION_PUBLISH_STATUSES = ("DRAFT", "PUBLISHED", "OFFLINE")
VERSION_PUBLISH_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"DRAFT", "PUBLISHED"},
    "PUBLISHED": {"PUBLISHED", "OFFLINE"},
    "OFFLINE": {"OFFLINE", "PUBLISHED"},
}


def gen_uuid(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def ok(data: Any) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "code": 0,
            "message": "success",
            "data": data,
        },
    )


def fail(code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "code": code,
            "message": message,
            "data": None,
        },
    )


class ApiError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@app.exception_handler(ApiError)
def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
    return fail(exc.code, exc.message)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or "demo"


def ensure(condition: bool, code: int, message: str) -> None:
    if not condition:
        raise ApiError(code, message)


def ensure_publish_status_transition(current_status: str, next_status: str) -> None:
    ensure(
        current_status in VERSION_PUBLISH_STATUSES,
        400,
        f"unsupported current publishStatus: {current_status}",
    )
    ensure(
        next_status in VERSION_PUBLISH_STATUSES,
        400,
        f"unsupported target publishStatus: {next_status}",
    )
    ensure(
        next_status in VERSION_PUBLISH_TRANSITIONS[current_status],
        400,
        (
            "invalid publishStatus transition: "
            f"{current_status} -> {next_status}; "
            "allowed transitions are DRAFT->PUBLISHED, PUBLISHED->OFFLINE, OFFLINE->PUBLISHED"
        ),
    )


def ensure_version_can_be_deployed(version: dict[str, Any]) -> None:
    ensure(
        version["publishStatus"] == "PUBLISHED",
        400,
        "only PUBLISHED versions can be deployed",
    )


def paginate(items: list[dict[str, Any]], page_num: int, page_size: int) -> dict[str, Any]:
    safe_page_num = max(page_num, 1)
    safe_page_size = max(page_size, 1)
    start = (safe_page_num - 1) * safe_page_size
    end = start + safe_page_size
    return {
        "items": items[start:end],
        "total": len(items),
        "pageNum": safe_page_num,
        "pageSize": safe_page_size,
    }


def algorithm_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "algorithmCode": item["algorithmCode"],
        "algorithmName": item["algorithmName"],
        "algorithmType": item["algorithmType"],
        "framework": item["framework"],
        "runtimeType": item["runtimeType"],
        "status": item["status"],
        "updatedAt": item["updatedAt"],
    }


def algorithm_detail(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "algorithmCode": item["algorithmCode"],
        "algorithmName": item["algorithmName"],
        "algorithmType": item["algorithmType"],
        "framework": item["framework"],
        "runtimeType": item["runtimeType"],
        "languageType": item["languageType"],
        "description": item["description"],
        "status": item["status"],
        "createdAt": item["createdAt"],
        "updatedAt": item["updatedAt"],
    }


def version_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "version": item["version"],
        "versionName": item["versionName"],
        "entrypoint": item["entrypoint"],
        "sourceType": item["sourceType"],
        "fullImageUri": item["fullImageUri"],
        "publishStatus": item["publishStatus"],
        "updatedAt": item["updatedAt"],
    }


def version_detail(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "algorithmUuid": item["algorithmUuid"],
        "version": item["version"],
        "versionName": item["versionName"],
        "entrypoint": item["entrypoint"],
        "codePath": item["codePath"],
        "configPath": item["configPath"],
        "changelog": item["changelog"],
        "sourceType": item["sourceType"],
        "localImageName": item["localImageName"],
        "imagePullPolicy": item["imagePullPolicy"],
        "registryUrl": item["registryUrl"],
        "repositoryName": item["repositoryName"],
        "imageTag": item["imageTag"],
        "imageDigest": item["imageDigest"],
        "fullImageUri": item["fullImageUri"],
        "imageSize": item["imageSize"],
        "publishStatus": item["publishStatus"],
        "createdAt": item["createdAt"],
        "updatedAt": item["updatedAt"],
    }

def deployment_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "versionUuid": item["versionUuid"],
        "namespace": item["namespace"],
        "deploymentName": item["deploymentName"],
        "serviceName": item["serviceName"],
        "status": item["status"],
        "image": item["image"],
        "accessEndpoint": item["accessEndpoint"],
        "replicas": item["replicas"],
        "readyReplicas": item["readyReplicas"],
        "port": item["port"],
        "is_deleted": item["is_deleted"],
        "updatedAt": item["updatedAt"],
    }


def deployment_detail(item: dict[str, Any]) -> dict[str, Any]:
    detail = deployment_summary(item)
    detail.update(
        {
            "errorMessage": item["errorMessage"],
            "deployedAt": item["deployedAt"],
        }
    )
    return detail


def build_record_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "algorithmUuid": item["algorithmUuid"],
        "baseVersionUuid": item["baseVersionUuid"],
        "outputVersionUuid": item["outputVersionUuid"],
        "buildStatus": item["buildStatus"],
        "operator": item["operator"],
        "startedAt": item["startedAt"],
        "finishedAt": item["finishedAt"],
    }


def build_record_detail(item: dict[str, Any]) -> dict[str, Any]:
    detail = build_record_summary(item)
    detail.update(
        {
            "buildSource": item["buildSource"],
            "sourceRevision": item["sourceRevision"],
            "configRevision": item["configRevision"],
            "imageTag": item["imageTag"],
            "imageDigest": item["imageDigest"],
            "fullImageUri": item["fullImageUri"],
            "buildLogPath": item["buildLogPath"],
            "errorMessage": item["errorMessage"],
            "resultSummary": item["resultSummary"],
        }
    )
    return detail


def deployment_endpoint(name: str, namespace: str, port: int) -> str:
    return f"http://{name}.{namespace}.svc.cluster.local:{port}"


def generate_unique_name(table: str, base: str, namespace: str) -> str:
    rows = fetch_all(
        """
        SELECT deploymentName
        FROM {}
        WHERE namespace = ? AND deploymentName LIKE ?
        """.format(table),
        (namespace, f"{base}%"),
    )
    used = {row["deploymentName"] for row in rows}
    index = 1
    candidate = f"{base}-{index}"
    while candidate in used:
        index += 1
        candidate = f"{base}-{index}"
    return candidate


def generate_deployment_name(algorithm_code: str, version: str, namespace: str) -> str:
    return generate_unique_name(
        "deployments",
        f"{slugify(algorithm_code)}-{slugify(version)}",
        namespace,
    )


def require_record(table: str, uuid: str, message: str) -> dict[str, Any]:
    item = fetch_one(f"SELECT * FROM {table} WHERE uuid = ?", (uuid,))
    ensure(item is not None, 404, message)
    return item  # type: ignore[return-value]


def require_algorithm(uuid: str) -> dict[str, Any]:
    return require_record("algorithms", uuid, "algorithm not found")


def require_version(uuid: str, message: str = "version not found") -> dict[str, Any]:
    return require_record("versions", uuid, message)


def require_build_record(uuid: str) -> dict[str, Any]:
    return require_record("build_records", uuid, "build record not found")


def require_deployment(uuid: str, message: str = "deployment not found") -> dict[str, Any]:
    item = fetch_one(
        "SELECT * FROM deployments WHERE uuid = ? AND is_deleted = 0",
        (uuid,),
    )
    ensure(item is not None, 404, message)
    return item  # type: ignore[return-value]


def touch_algorithm(uuid: str, updated_at: Any | None = None) -> None:
    execute(
        "UPDATE algorithms SET updatedAt = ? WHERE uuid = ?",
        (updated_at or now_db(), uuid),
    )


def touch_version(uuid: str, updated_at: Any | None = None) -> None:
    execute(
        "UPDATE versions SET updatedAt = ? WHERE uuid = ?",
        (updated_at or now_db(), uuid),
    )


def has_active_deployment(where_clause: str, params: tuple[Any, ...]) -> bool:
    row = fetch_one(
        f"""
        SELECT uuid
        FROM deployments
        WHERE is_deleted = 0 AND {where_clause} AND status IN ({ACTIVE_DEPLOYMENT_SQL})
        LIMIT 1
        """,
        params,
    )
    return row is not None


def resolve_version_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload["sourceType"] == "local":
        local_image_name = (payload.get("localImageName") or payload.get("fullImageUri") or "").strip()
        ensure(bool(local_image_name), 400, "localImageName is required for local images")
        if not payload.get("fullImageUri"):
            payload["fullImageUri"] = local_image_name
        payload["localImageName"] = local_image_name
        payload["imagePullPolicy"] = payload.get("imagePullPolicy") or "Never"
        payload["registryUrl"] = payload.get("registryUrl") or ""
        payload["repositoryName"] = payload.get("repositoryName") or ""
    else:
        ensure(bool(payload.get("fullImageUri")), 400, "fullImageUri is required for registry images")
        payload["localImageName"] = payload.get("localImageName") or ""
    return payload


def version_image_ref(version: dict[str, Any]) -> str:
    image_ref = (version.get("fullImageUri") or version.get("localImageName") or "").strip()
    ensure(bool(image_ref), 400, "version image is not configured")
    return image_ref


@app.post("/api/v1/algorithms")
def create_algorithm(body: CreateAlgorithmRequest):
    existing = fetch_one(
        "SELECT uuid FROM algorithms WHERE algorithmCode = ?",
        (body.algorithmCode,),
    )
    if existing:
        return fail(400, "algorithmCode already exists")

    algorithm_uuid = gen_uuid("alg")
    created_at = now_db()
    execute(
        """
        INSERT INTO algorithms (
            uuid, algorithmCode, algorithmName, algorithmType, framework,
            runtimeType, languageType, description, status, createdAt, updatedAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            algorithm_uuid,
            body.algorithmCode,
            body.algorithmName,
            body.algorithmType,
            body.framework or "",
            body.runtimeType or "",
            body.languageType or "",
            body.description or "",
            "ENABLED",
            created_at,
            created_at,
        ),
    )

    return ok(algorithm_detail(require_algorithm(algorithm_uuid)))


@app.get("/api/v1/algorithms")
def list_algorithms(
    keyword: str | None = Query(default=None),
    algorithmType: str | None = Query(default=None),
    pageNum: int = Query(default=1),
    pageSize: int = Query(default=10),
):
    rows = fetch_all("SELECT * FROM algorithms ORDER BY updatedAt DESC")
    items: list[dict[str, Any]] = []
    needle = keyword.lower() if keyword else None

    for item in rows:
        if algorithmType and item["algorithmType"] != algorithmType:
            continue
        if needle:
            haystack = " ".join(
                [item["algorithmCode"], item["algorithmName"], item["description"]]
            ).lower()
            if needle not in haystack:
                continue
        items.append(algorithm_summary(item))

    return ok(paginate(items, pageNum, pageSize))


@app.get("/api/v1/algorithms/{uuid}")
def get_algorithm(uuid: str):
    item = fetch_one("SELECT * FROM algorithms WHERE uuid = ?", (uuid,))
    if not item:
        return fail(404, "algorithm not found")
    return ok(algorithm_detail(item))


@app.put("/api/v1/algorithms/{uuid}")
def update_algorithm(uuid: str, body: UpdateAlgorithmRequest):
    item = fetch_one("SELECT * FROM algorithms WHERE uuid = ?", (uuid,))
    if not item:
        return fail(404, "algorithm not found")

    payload = body.model_dump(exclude_none=True)
    if "algorithmCode" in payload:
        existing = fetch_one(
            "SELECT uuid FROM algorithms WHERE algorithmCode = ? AND uuid != ?",
            (payload["algorithmCode"], uuid),
        )
        if existing:
            return fail(400, "algorithmCode already exists")

    if not payload:
        return ok(algorithm_detail(item))

    fields = []
    params: list[Any] = []
    for key, value in payload.items():
        fields.append(f"{key} = ?")
        params.append(value)
    fields.append("updatedAt = ?")
    params.append(now_db())
    params.append(uuid)

    execute(
        f"UPDATE algorithms SET {', '.join(fields)} WHERE uuid = ?",
        tuple(params),
    )
    updated = fetch_one("SELECT * FROM algorithms WHERE uuid = ?", (uuid,))
    return ok(algorithm_detail(updated))


@app.delete("/api/v1/algorithms/{uuid}")
def delete_algorithm(uuid: str):
    require_algorithm(uuid)
    active_deployment = fetch_one(
        """
        SELECT d.uuid
        FROM deployments d
        JOIN versions v ON v.uuid = d.versionUuid
        WHERE v.algorithmUuid = ? AND d.is_deleted = 0 AND d.status IN ({})
        LIMIT 1
        """.format(ACTIVE_DEPLOYMENT_SQL),
        (uuid,),
    )
    ensure(active_deployment is None, 400, "algorithm has active deployments")
    execute("DELETE FROM algorithms WHERE uuid = ?", (uuid,))
    return ok({"uuid": uuid})


@app.post("/api/v1/algorithms/{uuid}/versions")
def create_version(uuid: str, body: CreateVersionRequest):
    require_algorithm(uuid)
    payload = resolve_version_payload(body.model_dump())

    existing = fetch_one(
        "SELECT uuid FROM versions WHERE algorithmUuid = ? AND version = ?",
        (uuid, payload["version"]),
    )
    ensure(existing is None, 400, "version already exists under current algorithm")

    version_uuid = gen_uuid("ver")
    created_at = now_db()
    execute(
        """
        INSERT INTO versions (
            uuid, algorithmUuid, version, versionName, entrypoint,
            codePath, configPath, changelog, sourceType, localImageName,
            imagePullPolicy, registryUrl, repositoryName, imageTag,
            imageDigest, fullImageUri, imageSize, publishStatus, createdAt, updatedAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version_uuid,
            uuid,
            payload["version"],
            payload["versionName"] or payload["version"],
            payload["entrypoint"],
            payload["codePath"],
            payload["configPath"],
            payload["changelog"],
            payload["sourceType"],
            payload["localImageName"],
            payload["imagePullPolicy"],
            payload["registryUrl"],
            payload["repositoryName"],
            payload["imageTag"],
            payload["imageDigest"],
            payload["fullImageUri"],
            payload["imageSize"],
            "DRAFT",
            created_at,
            created_at,
        ),
    )
    touch_algorithm(uuid, created_at)

    return ok(version_detail(require_version(version_uuid)))


@app.get("/api/v1/algorithms/{uuid}/versions")
def list_versions(uuid: str):
    require_algorithm(uuid)
    rows = fetch_all(
        "SELECT * FROM versions WHERE algorithmUuid = ? ORDER BY updatedAt DESC",
        (uuid,),
    )
    items = [version_summary(item) for item in rows]
    return ok({"items": items, "total": len(items)})


@app.get("/api/v1/versions/{uuid}")
def get_version(uuid: str):
    return ok(version_detail(require_version(uuid)))


@app.put("/api/v1/versions/{uuid}")
def update_version(uuid: str, body: UpdateVersionRequest):
    item = require_version(uuid)

    payload = body.model_dump(exclude_none=True)
    if "publishStatus" in payload:
        ensure_publish_status_transition(item["publishStatus"], payload["publishStatus"])
        if item["publishStatus"] == "PUBLISHED" and payload["publishStatus"] == "OFFLINE":
            ensure(
                not has_active_deployment("versionUuid = ?", (uuid,)),
                400,
                "cannot offline version with active deployments",
            )
    merged_payload = dict(item)
    merged_payload.update(payload)
    merged_payload = resolve_version_payload(merged_payload)
    for key in (
        "sourceType",
        "localImageName",
        "imagePullPolicy",
        "registryUrl",
        "repositoryName",
        "imageTag",
        "imageDigest",
        "fullImageUri",
        "imageSize",
    ):
        payload[key] = merged_payload[key]
    if "version" in payload:
        existing = fetch_one(
            """
            SELECT uuid
            FROM versions
            WHERE algorithmUuid = ? AND version = ? AND uuid != ?
            """,
            (item["algorithmUuid"], payload["version"], uuid),
        )
        ensure(existing is None, 400, "version already exists under current algorithm")

    if not payload:
        return ok(version_detail(item))

    fields = []
    params: list[Any] = []
    for key, value in payload.items():
        fields.append(f"{key} = ?")
        params.append(value)
    fields.append("updatedAt = ?")
    updated_at = now_db()
    params.append(updated_at)
    params.append(uuid)

    execute(
        f"UPDATE versions SET {', '.join(fields)} WHERE uuid = ?",
        tuple(params),
    )
    touch_algorithm(item["algorithmUuid"], updated_at)
    return ok(version_detail(require_version(uuid)))


@app.delete("/api/v1/versions/{uuid}")
def delete_version(uuid: str):
    item = require_version(uuid)
    ensure(
        not has_active_deployment("versionUuid = ?", (uuid,)),
        400,
        "version has active deployments",
    )
    execute("DELETE FROM versions WHERE uuid = ?", (uuid,))
    touch_algorithm(item["algorithmUuid"])
    return ok({"uuid": uuid})


@app.post("/api/v1/deployments")
def create_deployment(body: CreateDeploymentRequest):
    version = require_version(body.versionUuid)
    ensure_version_can_be_deployed(version)
    algorithm = require_algorithm(version["algorithmUuid"])
    namespace = body.namespace
    deployment_name = generate_deployment_name(
        algorithm["algorithmCode"], version["version"], namespace
    )
    created_at = now_db()
    replicas = max(body.replicas, 1)
    resources = {}
    if body.resources:
        if body.resources.cpu is not None:
            resources["cpu"] = body.resources.cpu
        if body.resources.memory is not None:
            resources["memory"] = body.resources.memory

    item = {
        "uuid": gen_uuid("dep"),
        "versionUuid": body.versionUuid,
        "namespace": namespace,
        "deploymentName": deployment_name,
        "serviceName": f"{deployment_name}-svc",
        "status": "RUNNING",
        "image": version_image_ref(version),
        "port": body.port,
        "replicas": replicas,
        "readyReplicas": replicas,
        "accessEndpoint": deployment_endpoint(deployment_name, namespace, body.port),
        "errorMessage": "",
        "env": body.env,
        "resources": resources,
        "is_deleted": 0,
        "deployedAt": created_at,
        "updatedAt": created_at,
    }
    execute(
        """
        INSERT INTO deployments (
            uuid, versionUuid, namespace, deploymentName, serviceName,
            status, port, replicas, readyReplicas, accessEndpoint,
            errorMessage, env, resources, image, is_deleted, deployedAt, updatedAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item["uuid"],
            item["versionUuid"],
            item["namespace"],
            item["deploymentName"],
            item["serviceName"],
            item["status"],
            item["port"],
            item["replicas"],
            item["readyReplicas"],
            item["accessEndpoint"],
            item["errorMessage"],
            json_dumps(item["env"]),
            json_dumps(item["resources"]),
            item["image"],
            item["is_deleted"],
            item["deployedAt"],
            item["updatedAt"],
        ),
    )

    return ok(item)


@app.get("/api/v1/deployments")
def list_deployments(
    versionUuid: str | None = Query(default=None),
    namespace: str | None = Query(default=None),
    status: str | None = Query(default=None),
    pageNum: int = Query(default=1),
    pageSize: int = Query(default=10),
):
    rows = fetch_all(
        "SELECT * FROM deployments WHERE is_deleted = 0 ORDER BY updatedAt DESC"
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        item = parse_deployment(row)
        if versionUuid and item["versionUuid"] != versionUuid:
            continue
        if namespace and item["namespace"] != namespace:
            continue
        if status and item["status"] != status:
            continue
        items.append(deployment_summary(item))

    return ok(paginate(items, pageNum, pageSize))


@app.get("/api/v1/deployments/{uuid}")
def get_deployment(uuid: str):
    return ok(deployment_detail(parse_deployment(require_deployment(uuid))))


@app.put("/api/v1/deployments/{uuid}")
def update_deployment(uuid: str, body: UpdateDeploymentRequest):
    row = parse_deployment(require_deployment(uuid))
    payload = body.model_dump(exclude_none=True)
    if not payload:
        return ok(deployment_detail(row))

    next_version_uuid = payload.get("versionUuid", row["versionUuid"])
    next_version = require_version(next_version_uuid, "version not found")
    ensure_version_can_be_deployed(next_version)
    current_version = require_version(row["versionUuid"], "current version not found")
    ensure(
        next_version["algorithmUuid"] == current_version["algorithmUuid"],
        400,
        "target version does not belong to current algorithm",
    )

    next_port = payload.get("port", row["port"])
    next_env = payload.get("env", row["env"])
    next_resources = payload.get("resources", row["resources"])
    if hasattr(next_resources, "model_dump"):
        next_resources = next_resources.model_dump(exclude_none=True)

    execute(
        """
        UPDATE deployments
        SET versionUuid = ?, image = ?, port = ?, accessEndpoint = ?, env = ?, resources = ?, status = ?, updatedAt = ?
        WHERE uuid = ?
        """,
        (
            next_version_uuid,
            version_image_ref(next_version),
            next_port,
            deployment_endpoint(row["deploymentName"], row["namespace"], next_port),
            json_dumps(next_env),
            json_dumps(next_resources),
            "UPDATING",
            now_db(),
            uuid,
        ),
    )
    return ok(deployment_detail(parse_deployment(require_deployment(uuid))))


@app.delete("/api/v1/deployments/{uuid}")
def delete_deployment(uuid: str):
    require_deployment(uuid)
    updated_at = now_db()
    execute(
        """
        UPDATE deployments
        SET status = ?, readyReplicas = ?, is_deleted = ?, updatedAt = ?
        WHERE uuid = ?
        """,
        ("DELETED", 0, 1, updated_at, uuid),
    )
    return ok({"uuid": uuid, "status": "DELETED", "is_deleted": 1})


@app.post("/api/v1/deployments/{uuid}/restart")
def restart_deployment(uuid: str):
    row = require_deployment(uuid)
    ensure(row["status"] != "DELETED", 400, "deployment is deleted")

    execute(
        "UPDATE deployments SET status = ?, updatedAt = ? WHERE uuid = ?",
        ("UPDATING", now_db(), uuid),
    )
    return ok({"uuid": uuid, "status": "UPDATING"})


@app.post("/api/v1/deployments/{uuid}/scale")
def scale_deployment(uuid: str, body: ScaleRequest):
    row = require_deployment(uuid)
    ensure(body.replicas > 0, 400, "replicas must be greater than 0")

    execute(
        """
        UPDATE deployments
        SET status = ?, replicas = ?, readyReplicas = ?, updatedAt = ?
        WHERE uuid = ?
        """,
        ("SCALING", body.replicas, body.replicas, now_db(), uuid),
    )
    return ok(
        {
            "uuid": uuid,
            "namespace": row["namespace"],
            "deploymentName": row["deploymentName"],
            "status": "SCALING",
            "replicas": body.replicas,
        }
    )


@app.post("/api/v1/algorithms/{uuid}/build-records")
def create_build_record(uuid: str, body: CreateBuildRecordRequest):
    require_algorithm(uuid)
    if body.baseVersionUuid:
        base_version = require_version(body.baseVersionUuid, "base version not found")
        ensure(base_version["algorithmUuid"] == uuid, 400, "base version does not belong to current algorithm")
    if body.outputVersionUuid:
        output_version = require_version(body.outputVersionUuid, "output version not found")
        ensure(output_version["algorithmUuid"] == uuid, 400, "output version does not belong to current algorithm")

    started_at = now_db()
    finished_at = started_at if body.buildStatus in {"SUCCESS", "FAILED"} else None
    record_uuid = gen_uuid("bld")
    execute(
        """
        INSERT INTO build_records (
            uuid, algorithmUuid, baseVersionUuid, outputVersionUuid,
            buildStatus, operator, buildSource, sourceRevision, configRevision,
            imageTag, imageDigest, fullImageUri, startedAt, finishedAt,
            buildLogPath, errorMessage, resultSummary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_uuid,
            uuid,
            body.baseVersionUuid,
            body.outputVersionUuid,
            body.buildStatus,
            body.operator or "",
            body.buildSource,
            body.sourceRevision,
            body.configRevision,
            body.imageTag,
            body.imageDigest,
            body.fullImageUri,
            started_at,
            finished_at,
            body.buildLogPath or "",
            body.errorMessage or "",
            body.resultSummary or "",
        ),
    )
    return ok(build_record_detail(require_build_record(record_uuid)))


@app.get("/api/v1/algorithms/{uuid}/build-records")
def list_build_records(
    uuid: str,
    buildStatus: str | None = Query(default=None),
    pageNum: int = Query(default=1),
    pageSize: int = Query(default=10),
):
    require_algorithm(uuid)
    rows = fetch_all(
        "SELECT * FROM build_records WHERE algorithmUuid = ? ORDER BY startedAt DESC",
        (uuid,),
    )
    items: list[dict[str, Any]] = []
    for item in rows:
        if buildStatus and item["buildStatus"] != buildStatus:
            continue
        items.append(build_record_summary(item))
    return ok(paginate(items, pageNum, pageSize))


@app.get("/api/v1/build-records/{uuid}")
def get_build_record(uuid: str):
    return ok(build_record_detail(require_build_record(uuid)))


@app.put("/api/v1/build-records/{uuid}")
def update_build_record(uuid: str, body: UpdateBuildRecordRequest):
    item = require_build_record(uuid)
    payload = body.model_dump(exclude_none=True)
    if "outputVersionUuid" in payload:
        output_version = require_version(payload["outputVersionUuid"], "output version not found")
        ensure(output_version["algorithmUuid"] == item["algorithmUuid"], 400, "output version does not belong to current algorithm")
    if not payload:
        return ok(build_record_detail(item))
    if payload.get("buildStatus") in {"SUCCESS", "FAILED"} and "finishedAt" not in payload:
        payload["finishedAt"] = now_db()
    elif "finishedAt" in payload:
        payload["finishedAt"] = to_db_datetime(payload["finishedAt"])

    fields = []
    params: list[Any] = []
    for key, value in payload.items():
        fields.append(f"{key} = ?")
        params.append(value)
    params.append(uuid)
    execute(
        f"UPDATE build_records SET {', '.join(fields)} WHERE uuid = ?",
        tuple(params),
    )
    return ok(build_record_detail(require_build_record(uuid)))


@app.delete("/api/v1/build-records/{uuid}")
def delete_build_record(uuid: str):
    require_build_record(uuid)
    execute("DELETE FROM build_records WHERE uuid = ?", (uuid,))
    return ok({"uuid": uuid})


@app.get("/health")
def health():
    return {"status": "ok", "database": str(DB_PATH)}
