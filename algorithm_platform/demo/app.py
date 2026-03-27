import re
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db import (
    DB_PATH,
    ensure_database,
    execute,
    fetch_all,
    fetch_one,
    json_dumps,
    now_iso,
    parse_container,
    parse_deployment,
    parse_image,
)
from models import (
    CreateAlgorithmRequest,
    CreateContainerRequest,
    CreateDebugSessionRequest,
    CreateDeploymentRequest,
    CreateImageRequest,
    CreateVersionRequest,
    HotUpdateRequest,
    ScaleRequest,
    UpdateAlgorithmRequest,
    UpdateVersionRequest,
)
from runtime import (
    MUTABLE_DEBUG_SESSION_STATUSES,
    delete_session_runtime,
    provision_debug_session,
    run_hot_update_job,
    runtime_path_for_session,
    stop_debug_process,
    sync_session_state_file,
    update_debug_session,
)


app = FastAPI(
    title="光电感知系统 Demo Backend",
    version="0.6.0",
    description="按 Apifox 导出文档整理的 Python/FastAPI demo 后端，使用 SQLite 持久化存储",
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
ACTIVE_HOT_UPDATE_STATUSES = ("PENDING", "RUNNING")
ACTIVE_DEPLOYMENT_SQL = ", ".join(f"'{status}'" for status in ACTIVE_DEPLOYMENT_STATUSES)
ACTIVE_HOT_UPDATE_SQL = ", ".join(f"'{status}'" for status in ACTIVE_HOT_UPDATE_STATUSES)


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
        "configPath": item["configPath"],
        "changelog": item["changelog"],
        "publishStatus": item["publishStatus"],
        "createdAt": item["createdAt"],
        "updatedAt": item["updatedAt"],
    }


def image_detail(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "algorithmVersionUuid": item["algorithmVersionUuid"],
        "registryUrl": item["registryUrl"],
        "repositoryName": item["repositoryName"],
        "imageTag": item["imageTag"],
        "imageDigest": item["imageDigest"],
        "fullImageUri": item["fullImageUri"],
        "imageSize": item["imageSize"],
        "isAvailable": item["isAvailable"],
        "createdAt": item["createdAt"],
    }


def deployment_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "algorithmVersionUuid": item["algorithmVersionUuid"],
        "imageUuid": item["imageUuid"],
        "namespace": item["namespace"],
        "deploymentName": item["deploymentName"],
        "serviceName": item["serviceName"],
        "status": item["status"],
        "accessEndpoint": item["accessEndpoint"],
        "replicas": item["replicas"],
        "readyReplicas": item["readyReplicas"],
        "port": item["port"],
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


def debug_session_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "sessionName": item["sessionName"],
        "namespace": item["namespace"],
        "podName": item["podName"],
        "currentVersionUuid": item["currentVersionUuid"],
        "debugStatus": item["debugStatus"],
        "processPid": item.get("processPid"),
        "lastError": item["lastError"],
        "createdAt": item["createdAt"],
        "updatedAt": item["updatedAt"],
    }


def debug_session_detail(item: dict[str, Any]) -> dict[str, Any]:
    detail = debug_session_summary(item)
    detail.update(
        {
            "algorithmUuid": item["algorithmUuid"],
            "baseVersionUuid": item["baseVersionUuid"],
            "runtimePath": item["runtimePath"],
        }
    )
    return detail


def hot_update_detail(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": item["uuid"],
        "fromVersionUuid": item["fromVersionUuid"],
        "toVersionUuid": item["toVersionUuid"],
        "updateType": item["updateType"],
        "updateStatus": item["updateStatus"],
        "operator": item["operator"],
        "startedAt": item["startedAt"],
        "finishedAt": item["finishedAt"],
        "errorMessage": item["errorMessage"],
        "resultSummary": item["resultSummary"],
        "actionLogPath": item["actionLogPath"],
    }


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


def generate_container_name(name: str, version: str | None, namespace: str) -> str:
    return generate_unique_name(
        "containers",
        f"{slugify(name)}-{slugify(version or 'v1')}",
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


def require_image(uuid: str) -> dict[str, Any]:
    return parse_image(require_record("images", uuid, "image not found"))


def require_debug_session(uuid: str) -> dict[str, Any]:
    return require_record("debug_sessions", uuid, "debug session not found")


def touch_algorithm(uuid: str, updated_at: str | None = None) -> None:
    execute(
        "UPDATE algorithms SET updatedAt = ? WHERE uuid = ?",
        (updated_at or now_iso(), uuid),
    )


def touch_version(uuid: str, updated_at: str | None = None) -> None:
    execute(
        "UPDATE versions SET updatedAt = ? WHERE uuid = ?",
        (updated_at or now_iso(), uuid),
    )


def has_active_deployment(where_clause: str, params: tuple[Any, ...]) -> bool:
    row = fetch_one(
        f"""
        SELECT uuid
        FROM deployments
        WHERE {where_clause} AND status IN ({ACTIVE_DEPLOYMENT_SQL})
        LIMIT 1
        """,
        params,
    )
    return row is not None


def has_active_hot_update(session_uuid: str) -> bool:
    row = fetch_one(
        f"""
        SELECT uuid
        FROM hot_updates
        WHERE debugSessionUuid = ? AND updateStatus IN ({ACTIVE_HOT_UPDATE_SQL})
        LIMIT 1
        """,
        (session_uuid,),
    )
    return row is not None


def has_container_reference(column: str, uuid: str) -> bool:
    row = fetch_one(f"SELECT uuid FROM containers WHERE {column} = ? LIMIT 1", (uuid,))
    return row is not None


def has_debug_session_reference(version_uuid: str) -> bool:
    row = fetch_one(
        """
        SELECT uuid
        FROM debug_sessions
        WHERE baseVersionUuid = ? OR currentVersionUuid = ?
        LIMIT 1
        """,
        (version_uuid, version_uuid),
    )
    return row is not None


def ensure_image_matches_version(image: dict[str, Any], version_uuid: str) -> None:
    ensure(
        image["algorithmVersionUuid"] == version_uuid,
        400,
        "image does not belong to current version",
    )


def ensure_image_available(image: dict[str, Any]) -> None:
    ensure(image["isAvailable"], 400, "image is offline")


@app.post("/api/v1/algorithms")
def create_algorithm(body: CreateAlgorithmRequest):
    existing = fetch_one(
        "SELECT uuid FROM algorithms WHERE algorithmCode = ?",
        (body.algorithmCode,),
    )
    if existing:
        return fail(400, "algorithmCode already exists")

    algorithm_uuid = gen_uuid("alg")
    created_at = now_iso()
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

    return ok(
        {
            "uuid": algorithm_uuid,
            "algorithmCode": body.algorithmCode,
            "algorithmName": body.algorithmName,
            "algorithmType": body.algorithmType,
            "framework": body.framework or "",
            "runtimeType": body.runtimeType or "",
            "languageType": body.languageType or "",
            "status": "ENABLED",
            "createdAt": created_at,
        }
    )


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
    params.append(now_iso())
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
        JOIN versions v ON v.uuid = d.algorithmVersionUuid
        WHERE v.algorithmUuid = ? AND d.status IN ({})
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

    existing = fetch_one(
        "SELECT uuid FROM versions WHERE algorithmUuid = ? AND version = ?",
        (uuid, body.version),
    )
    ensure(existing is None, 400, "version already exists under current algorithm")

    version_uuid = gen_uuid("ver")
    created_at = now_iso()
    execute(
        """
        INSERT INTO versions (
            uuid, algorithmUuid, version, versionName, entrypoint,
            configPath, changelog, publishStatus, createdAt, updatedAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version_uuid,
            uuid,
            body.version,
            body.versionName or body.version,
            body.entrypoint,
            body.configPath,
            body.changelog,
            "DRAFT",
            created_at,
            created_at,
        ),
    )
    touch_algorithm(uuid, created_at)

    return ok(
        {
            "uuid": version_uuid,
            "algorithmUuid": uuid,
            "version": body.version,
            "versionName": body.versionName or body.version,
            "entrypoint": body.entrypoint,
            "configPath": body.configPath,
            "publishStatus": "DRAFT",
            "createdAt": created_at,
        }
    )


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
    updated_at = now_iso()
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
        not has_active_deployment("algorithmVersionUuid = ?", (uuid,)),
        400,
        "version has active deployments",
    )
    ensure(
        not has_container_reference("algorithmVersionUuid", uuid),
        400,
        "version is referenced by container deployment",
    )
    ensure(
        not has_debug_session_reference(uuid),
        400,
        "version is referenced by debug session",
    )
    execute("DELETE FROM versions WHERE uuid = ?", (uuid,))
    touch_algorithm(item["algorithmUuid"])
    return ok({"uuid": uuid})


@app.post("/api/v1/versions/{uuid}/images")
def create_image(uuid: str, body: CreateImageRequest):
    require_version(uuid, "algorithm version not found")

    image_uuid = gen_uuid("img")
    created_at = now_iso()
    execute(
        """
        INSERT INTO images (
            uuid, algorithmVersionUuid, registryUrl, repositoryName, imageTag,
            imageDigest, fullImageUri, imageSize, isAvailable, createdAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            image_uuid,
            uuid,
            body.registryUrl,
            body.repositoryName,
            body.imageTag,
            body.imageDigest,
            body.fullImageUri,
            body.imageSize,
            1,
            created_at,
        ),
    )
    touch_version(uuid, created_at)

    return ok(
        {
            "uuid": image_uuid,
            "algorithmVersionUuid": uuid,
            "fullImageUri": body.fullImageUri,
            "isAvailable": True,
            "createdAt": created_at,
        }
    )


@app.get("/api/v1/versions/{uuid}/images")
def list_images(uuid: str):
    require_version(uuid, "algorithm version not found")
    rows = fetch_all(
        "SELECT * FROM images WHERE algorithmVersionUuid = ? ORDER BY createdAt DESC",
        (uuid,),
    )
    items = []
    for row in rows:
        item = parse_image(row)
        items.append(
            {
                "uuid": item["uuid"],
                "fullImageUri": item["fullImageUri"],
                "imageTag": item["imageTag"],
                "imageDigest": item["imageDigest"],
                "imageSize": item["imageSize"],
                "isAvailable": item["isAvailable"],
                "createdAt": item["createdAt"],
            }
        )
    return ok({"items": items, "total": len(items)})


@app.get("/api/v1/images/{uuid}")
def get_image(uuid: str):
    return ok(image_detail(require_image(uuid)))


def mark_image_offline(uuid: str) -> JSONResponse:
    image = require_image(uuid)
    ensure(
        not has_active_deployment("imageUuid = ?", (uuid,)),
        400,
        "image has active deployments",
    )
    ensure(
        not has_container_reference("imageUuid", uuid),
        400,
        "image is referenced by container deployment",
    )

    if image["isAvailable"]:
        updated_at = now_iso()
        execute("UPDATE images SET isAvailable = ? WHERE uuid = ?", (0, uuid))
        touch_version(image["algorithmVersionUuid"], updated_at)

    return ok(image_detail(require_image(uuid)))


@app.delete("/api/v1/images/{uuid}")
def delete_image(uuid: str):
    return mark_image_offline(uuid)


@app.post("/api/v1/images/{uuid}/offline")
def offline_image(uuid: str):
    return mark_image_offline(uuid)


@app.post("/api/v1/deployments")
def create_deployment(body: CreateDeploymentRequest):
    version = require_version(body.algorithmVersionUuid)
    image = require_image(body.imageUuid)
    ensure_image_matches_version(image, body.algorithmVersionUuid)
    ensure_image_available(image)
    algorithm = require_algorithm(version["algorithmUuid"])
    namespace = body.namespace
    deployment_name = generate_deployment_name(
        algorithm["algorithmCode"], version["version"], namespace
    )
    created_at = now_iso()
    replicas = max(body.replicas, 1)
    resources = {}
    if body.resources:
        if body.resources.cpu is not None:
            resources["cpu"] = body.resources.cpu
        if body.resources.memory is not None:
            resources["memory"] = body.resources.memory

    item = {
        "uuid": gen_uuid("dep"),
        "algorithmVersionUuid": body.algorithmVersionUuid,
        "imageUuid": body.imageUuid,
        "namespace": namespace,
        "deploymentName": deployment_name,
        "serviceName": f"{deployment_name}-svc",
        "status": "RUNNING",
        "port": body.port,
        "replicas": replicas,
        "readyReplicas": replicas,
        "accessEndpoint": deployment_endpoint(deployment_name, namespace, body.port),
        "errorMessage": "",
        "env": body.env,
        "resources": resources,
        "deployedAt": created_at,
        "updatedAt": created_at,
    }
    execute(
        """
        INSERT INTO deployments (
            uuid, algorithmVersionUuid, imageUuid, namespace, deploymentName,
            serviceName, status, port, replicas, readyReplicas, accessEndpoint,
            errorMessage, env, resources, deployedAt, updatedAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item["uuid"],
            item["algorithmVersionUuid"],
            item["imageUuid"],
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
            item["deployedAt"],
            item["updatedAt"],
        ),
    )

    return ok(item)


@app.get("/api/v1/deployments")
def list_deployments(
    algorithmVersionUuid: str | None = Query(default=None),
    namespace: str | None = Query(default=None),
    status: str | None = Query(default=None),
    pageNum: int = Query(default=1),
    pageSize: int = Query(default=10),
):
    rows = fetch_all("SELECT * FROM deployments ORDER BY updatedAt DESC")
    items: list[dict[str, Any]] = []
    for row in rows:
        item = parse_deployment(row)
        if algorithmVersionUuid and item["algorithmVersionUuid"] != algorithmVersionUuid:
            continue
        if namespace and item["namespace"] != namespace:
            continue
        if status and item["status"] != status:
            continue
        items.append(deployment_summary(item))

    return ok(paginate(items, pageNum, pageSize))


@app.get("/api/v1/deployments/{uuid}")
def get_deployment(uuid: str):
    return ok(deployment_detail(parse_deployment(require_record("deployments", uuid, "deployment not found"))))


@app.delete("/api/v1/deployments/{uuid}")
def delete_deployment(uuid: str):
    require_record("deployments", uuid, "deployment not found")
    updated_at = now_iso()
    execute(
        """
        UPDATE deployments
        SET status = ?, readyReplicas = ?, updatedAt = ?
        WHERE uuid = ?
        """,
        ("DELETING", 0, updated_at, uuid),
    )
    return ok({"uuid": uuid, "status": "DELETING"})


@app.post("/api/v1/deployments/{uuid}/restart")
def restart_deployment(uuid: str):
    row = require_record("deployments", uuid, "deployment not found")
    ensure(row["status"] != "DELETING", 400, "deployment is deleting")

    execute(
        "UPDATE deployments SET status = ?, updatedAt = ? WHERE uuid = ?",
        ("UPDATING", now_iso(), uuid),
    )
    return ok({"uuid": uuid, "status": "UPDATING"})


@app.post("/api/v1/deployments/{uuid}/scale")
def scale_deployment(uuid: str, body: ScaleRequest):
    row = require_record("deployments", uuid, "deployment not found")
    ensure(body.replicas > 0, 400, "replicas must be greater than 0")

    execute(
        """
        UPDATE deployments
        SET status = ?, replicas = ?, readyReplicas = ?, updatedAt = ?
        WHERE uuid = ?
        """,
        ("SCALING", body.replicas, body.replicas, now_iso(), uuid),
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


@app.post("/api/v1/debug-sessions")
def create_debug_session(body: CreateDebugSessionRequest, background_tasks: BackgroundTasks):
    require_algorithm(body.algorithmUuid)
    base_version = require_version(body.baseVersionUuid, "base version not found")
    ensure(
        base_version["algorithmUuid"] == body.algorithmUuid,
        400,
        "base version does not belong to current algorithm",
    )

    created_at = now_iso()
    session_uuid = gen_uuid("dbg")
    runtime_path = str(runtime_path_for_session(session_uuid))
    session = {
        "uuid": session_uuid,
        "algorithmUuid": body.algorithmUuid,
        "baseVersionUuid": body.baseVersionUuid,
        "currentVersionUuid": body.baseVersionUuid,
        "sessionName": body.sessionName,
        "namespace": body.namespace,
        "podName": f"{slugify(body.sessionName)}-pod",
        "debugStatus": "PENDING",
        "runtimePath": runtime_path,
        "processPid": None,
        "lastError": "",
        "createdAt": created_at,
        "updatedAt": created_at,
    }
    execute(
        """
        INSERT INTO debug_sessions (
            uuid, algorithmUuid, baseVersionUuid, currentVersionUuid,
            sessionName, namespace, podName, debugStatus, runtimePath,
            processPid, lastError, createdAt, updatedAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session["uuid"],
            session["algorithmUuid"],
            session["baseVersionUuid"],
            session["currentVersionUuid"],
            session["sessionName"],
            session["namespace"],
            session["podName"],
            session["debugStatus"],
            session["runtimePath"],
            session["processPid"],
            session["lastError"],
            session["createdAt"],
            session["updatedAt"],
        ),
    )
    sync_session_state_file(session_uuid)
    background_tasks.add_task(provision_debug_session, session_uuid)
    return ok(debug_session_detail(session))


@app.get("/api/v1/debug-sessions")
def list_debug_sessions(
    namespace: str | None = Query(default=None),
    pageNum: int = Query(default=1),
    pageSize: int = Query(default=10),
):
    rows = fetch_all("SELECT * FROM debug_sessions ORDER BY createdAt DESC")
    items: list[dict[str, Any]] = []
    for item in rows:
        if namespace and item["namespace"] != namespace:
            continue
        items.append(debug_session_summary(item))
    return ok(paginate(items, pageNum, pageSize))


@app.get("/api/v1/debug-sessions/{uuid}")
def get_debug_session(uuid: str):
    return ok(debug_session_detail(require_debug_session(uuid)))


@app.post("/api/v1/debug-sessions/{uuid}/close")
def close_debug_session(uuid: str):
    item = require_debug_session(uuid)
    ensure(not has_active_hot_update(uuid), 400, "debug session has active hot update")

    stop_debug_process(item.get("processPid"))
    update_debug_session(uuid, debugStatus="SUCCESS", processPid=None, lastError="")
    sync_session_state_file(uuid)
    return ok(debug_session_detail(require_debug_session(uuid)))


@app.delete("/api/v1/debug-sessions/{uuid}")
def delete_debug_session(uuid: str):
    item = require_debug_session(uuid)
    stop_debug_process(item.get("processPid"))
    execute("DELETE FROM debug_sessions WHERE uuid = ?", (uuid,))
    delete_session_runtime(uuid)
    return ok({"uuid": uuid})


@app.post("/api/v1/debug-sessions/{uuid}/hot-update")
def trigger_hot_update(
    uuid: str,
    body: HotUpdateRequest,
    background_tasks: BackgroundTasks,
):
    session = require_debug_session(uuid)
    ensure(
        session["debugStatus"] in MUTABLE_DEBUG_SESSION_STATUSES,
        400,
        "debug session is not ready for hot update",
    )
    target_version = require_version(body.toVersionUuid, "target version not found")
    ensure(
        target_version["algorithmUuid"] == session["algorithmUuid"],
        400,
        "target version does not belong to current algorithm",
    )
    ensure(
        body.toVersionUuid != session["currentVersionUuid"],
        400,
        "target version is same as current version",
    )
    ensure(
        not has_active_hot_update(uuid),
        400,
        "debug session already has an active hot update",
    )

    started_at = now_iso()
    hot_item = {
        "uuid": gen_uuid("hot"),
        "debugSessionUuid": uuid,
        "fromVersionUuid": session["currentVersionUuid"],
        "toVersionUuid": body.toVersionUuid,
        "updateType": body.updateType,
        "updateStatus": "PENDING",
        "operator": body.operator,
        "startedAt": started_at,
        "finishedAt": "",
        "errorMessage": "",
        "resultSummary": "hot update queued",
        "actionLogPath": "",
    }
    update_debug_session(uuid, debugStatus="PENDING", lastError="")
    sync_session_state_file(uuid)
    execute(
        """
        INSERT INTO hot_updates (
            uuid, debugSessionUuid, fromVersionUuid, toVersionUuid,
            updateType, updateStatus, operator, startedAt, finishedAt,
            errorMessage, resultSummary, actionLogPath
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            hot_item["uuid"],
            hot_item["debugSessionUuid"],
            hot_item["fromVersionUuid"],
            hot_item["toVersionUuid"],
            hot_item["updateType"],
            hot_item["updateStatus"],
            hot_item["operator"],
            hot_item["startedAt"],
            hot_item["finishedAt"],
            hot_item["errorMessage"],
            hot_item["resultSummary"],
            hot_item["actionLogPath"],
        ),
    )
    background_tasks.add_task(run_hot_update_job, hot_item["uuid"])
    return ok(hot_update_detail(hot_item))


@app.get("/api/v1/debug-sessions/{uuid}/hot-updates")
def list_hot_updates(
    uuid: str,
    pageNum: int = Query(default=1),
    pageSize: int = Query(default=10),
):
    require_debug_session(uuid)
    items = fetch_all(
        """
        SELECT uuid, fromVersionUuid, toVersionUuid, updateType,
               updateStatus, operator, startedAt, finishedAt,
               errorMessage, resultSummary, actionLogPath
        FROM hot_updates
        WHERE debugSessionUuid = ?
        ORDER BY startedAt DESC
        """,
        (uuid,),
    )
    return ok(paginate([hot_update_detail(item) for item in items], pageNum, pageSize))


@app.post("/api/v1/containers/start")
def start_container(body: CreateContainerRequest):
    version = require_version(body.algorithmVersionUuid)
    image = require_image(body.imageUuid)
    ensure_image_matches_version(image, body.algorithmVersionUuid)
    ensure_image_available(image)

    namespace = body.namespace
    container_uuid = gen_uuid("ctr")
    container_version = body.version or version["version"]
    container_image = body.image or image["fullImageUri"]
    deployment_name = generate_container_name(body.name, container_version, namespace)
    service_name = f"{deployment_name}-svc"
    created_at = now_iso()

    execute(
        """
        INSERT INTO containers (
            uuid, algorithmVersionUuid, imageUuid, name, version, image,
            namespace, port, replicas, readyReplicas, env, cpu, memory,
            deploymentName, serviceName, status, createdAt, updatedAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            container_uuid,
            body.algorithmVersionUuid,
            body.imageUuid,
            body.name,
            container_version,
            container_image,
            namespace,
            body.port,
            body.replicas,
            body.replicas,
            json_dumps(body.env),
            body.cpu,
            body.memory,
            deployment_name,
            service_name,
            "Running",
            created_at,
            created_at,
        ),
    )

    return ok(
        {
            "uuid": container_uuid,
            "deploymentName": deployment_name,
            "serviceName": service_name,
        }
    )


@app.get("/api/v1/containers")
def list_containers(
    namespace: str | None = Query(default="default"),
    pageNum: int = Query(default=1),
    pageSize: int = Query(default=10),
):
    target_namespace = namespace or "default"
    rows = fetch_all(
        "SELECT * FROM containers WHERE namespace = ? ORDER BY createdAt DESC",
        (target_namespace,),
    )
    items = []
    for row in rows:
        item = parse_container(row)
        items.append(
            {
                "uuid": item["uuid"],
                "name": item["name"],
                "namespace": item["namespace"],
                "deploymentName": item["deploymentName"],
                "serviceName": item["serviceName"],
                "status": item["status"],
                "image": item["image"],
                "replicas": item["replicas"],
                "readyReplicas": item["readyReplicas"],
                "algorithmVersionUuid": item["algorithmVersionUuid"],
                "imageUuid": item["imageUuid"],
                "updatedAt": item["updatedAt"],
            }
        )
    return ok(paginate(items, pageNum, pageSize))


@app.delete("/api/v1/containers/{name}")
def delete_container(name: str, namespace: str | None = Query(default="default")):
    target_namespace = namespace or "default"
    row = fetch_one(
        "SELECT uuid, deploymentName FROM containers WHERE namespace = ? AND deploymentName = ?",
        (target_namespace, name),
    )
    if not row:
        return fail(404, "container not found")

    execute(
        "DELETE FROM containers WHERE namespace = ? AND deploymentName = ?",
        (target_namespace, name),
    )
    return ok({"deploymentName": row["deploymentName"], "namespace": target_namespace})


@app.post("/api/v1/containers/{name}/restart")
def restart_container(name: str, namespace: str | None = Query(default="default")):
    target_namespace = namespace or "default"
    row = fetch_one(
        "SELECT deploymentName FROM containers WHERE namespace = ? AND deploymentName = ?",
        (target_namespace, name),
    )
    if not row:
        return fail(404, "container not found")

    execute(
        """
        UPDATE containers
        SET status = ?, updatedAt = ?
        WHERE namespace = ? AND deploymentName = ?
        """,
        ("Running", now_iso(), target_namespace, name),
    )
    return ok({"deploymentName": row["deploymentName"], "namespace": target_namespace})


@app.post("/api/v1/containers/{name}/scale")
def scale_container(
    name: str,
    body: ScaleRequest,
    namespace: str | None = Query(default="default"),
):
    target_namespace = namespace or "default"
    row = fetch_one(
        "SELECT name FROM containers WHERE namespace = ? AND deploymentName = ?",
        (target_namespace, name),
    )
    if not row:
        return fail(404, "container not found")
    if body.replicas <= 0:
        return fail(400, "replicas must be greater than 0")

    execute(
        """
        UPDATE containers
        SET replicas = ?, readyReplicas = ?, updatedAt = ?
        WHERE namespace = ? AND deploymentName = ?
        """,
        (body.replicas, body.replicas, now_iso(), target_namespace, name),
    )
    return ok(
        {
            "name": row["name"],
            "namespace": target_namespace,
            "replicas": body.replicas,
        }
    )


@app.get("/health")
def health():
    return {"status": "ok", "database": str(DB_PATH)}
