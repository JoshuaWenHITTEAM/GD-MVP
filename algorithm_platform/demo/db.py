import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pymysql


TZ = timezone(timedelta(hours=8))
BASE_DIR = Path(__file__).resolve().parent
RUNTIME_ROOT = BASE_DIR / "runtime"
SCHEMA_VERSION = "2026-04-09-mysql"

DB_HOST = os.getenv("DEMO_DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DEMO_DB_PORT", "3306"))
DB_USER = os.getenv("DEMO_DB_USER", "lurunda")
DB_PASSWORD = os.getenv("DEMO_DB_PASSWORD", "G7v!Q2m#L9x@R4pZ")
DB_NAME = os.getenv("DEMO_DB_NAME", "algo_manager")
DB_CHARSET = "utf8mb4"
DB_PATH = f"mysql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS app_meta (
        `key` VARCHAR(64) PRIMARY KEY,
        `value` VARCHAR(255) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS algorithms (
        uuid VARCHAR(64) PRIMARY KEY,
        algorithmCode VARCHAR(64) NOT NULL UNIQUE,
        algorithmName VARCHAR(128) NOT NULL,
        algorithmType VARCHAR(64) NOT NULL,
        framework VARCHAR(64) NOT NULL,
        runtimeType VARCHAR(32) NOT NULL,
        languageType VARCHAR(32) NOT NULL,
        description TEXT NOT NULL,
        status VARCHAR(32) NOT NULL,
        createdAt VARCHAR(64) NOT NULL,
        updatedAt VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS versions (
        uuid VARCHAR(64) PRIMARY KEY,
        algorithmUuid VARCHAR(64) NOT NULL,
        version VARCHAR(64) NOT NULL,
        versionName VARCHAR(128) NOT NULL,
        entrypoint VARCHAR(255) NOT NULL,
        codePath VARCHAR(255) NOT NULL,
        configPath VARCHAR(255) NOT NULL,
        changelog TEXT NOT NULL,
        sourceType VARCHAR(32) NOT NULL,
        localImageName VARCHAR(255) NOT NULL,
        imagePullPolicy VARCHAR(32) NOT NULL,
        registryUrl VARCHAR(255) NOT NULL,
        repositoryName VARCHAR(255) NOT NULL,
        imageTag VARCHAR(128) NOT NULL,
        imageDigest VARCHAR(255) NULL,
        fullImageUri VARCHAR(512) NOT NULL,
        imageSize BIGINT NULL,
        publishStatus VARCHAR(32) NOT NULL,
        createdAt VARCHAR(64) NOT NULL,
        updatedAt VARCHAR(64) NOT NULL,
        UNIQUE KEY uniq_algorithm_version (algorithmUuid, version),
        CONSTRAINT fk_versions_algorithm
            FOREIGN KEY (algorithmUuid) REFERENCES algorithms(uuid)
            ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS deployments (
        uuid VARCHAR(64) PRIMARY KEY,
        versionUuid VARCHAR(64) NOT NULL,
        namespace VARCHAR(64) NOT NULL,
        deploymentName VARCHAR(128) NOT NULL,
        serviceName VARCHAR(128) NOT NULL,
        status VARCHAR(32) NOT NULL,
        port INT NOT NULL,
        replicas INT NOT NULL,
        readyReplicas INT NOT NULL,
        accessEndpoint VARCHAR(255) NOT NULL,
        errorMessage TEXT NOT NULL,
        env TEXT NOT NULL,
        resources TEXT NOT NULL,
        image VARCHAR(512) NOT NULL,
        deployedAt VARCHAR(64) NOT NULL,
        updatedAt VARCHAR(64) NOT NULL,
        UNIQUE KEY uniq_namespace_deployment (namespace, deploymentName),
        CONSTRAINT fk_deployments_version
            FOREIGN KEY (versionUuid) REFERENCES versions(uuid)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS build_records (
        uuid VARCHAR(64) PRIMARY KEY,
        algorithmUuid VARCHAR(64) NOT NULL,
        baseVersionUuid VARCHAR(64) NULL,
        outputVersionUuid VARCHAR(64) NULL,
        buildStatus VARCHAR(32) NOT NULL,
        operator VARCHAR(64) NOT NULL,
        buildSource VARCHAR(255) NULL,
        sourceRevision VARCHAR(255) NULL,
        configRevision VARCHAR(255) NULL,
        imageTag VARCHAR(128) NULL,
        imageDigest VARCHAR(255) NULL,
        fullImageUri VARCHAR(512) NULL,
        startedAt VARCHAR(64) NOT NULL,
        finishedAt VARCHAR(64) NOT NULL,
        buildLogPath VARCHAR(255) NOT NULL,
        errorMessage TEXT NOT NULL,
        resultSummary TEXT NOT NULL,
        CONSTRAINT fk_build_records_algorithm
            FOREIGN KEY (algorithmUuid) REFERENCES algorithms(uuid)
            ON DELETE CASCADE,
        CONSTRAINT fk_build_records_base_version
            FOREIGN KEY (baseVersionUuid) REFERENCES versions(uuid),
        CONSTRAINT fk_build_records_output_version
            FOREIGN KEY (outputVersionUuid) REFERENCES versions(uuid)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]

RESET_TABLES = [
    "build_records",
    "deployments",
    "versions",
    "algorithms",
    "app_meta",
]


def now_iso() -> str:
    return datetime.now(TZ).isoformat()


def json_dumps(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, separators=(",", ":"))


def json_loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    return json.loads(value)


def _normalize_query(query: str) -> str:
    return query.replace("?", "%s")


def _connect(*, use_database: bool = True, autocommit: bool = False) -> pymysql.connections.Connection:
    params: dict[str, Any] = {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "charset": DB_CHARSET,
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": autocommit,
    }
    if use_database:
        params["database"] = DB_NAME
    return pymysql.connect(**params)


def get_conn() -> pymysql.connections.Connection:
    return _connect(use_database=True, autocommit=False)


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(_normalize_query(query), params)
            row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(_normalize_query(query), params)
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def execute(query: str, params: tuple[Any, ...] = ()) -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(_normalize_query(query), params)
        conn.commit()
    finally:
        conn.close()


def update_by_uuid(table: str, uuid: str, values: dict[str, Any]) -> None:
    if not values:
        return

    assignments = ", ".join(f"{key} = %s" for key in values)
    params = tuple(values.values()) + (uuid,)
    execute(f"UPDATE {table} SET {assignments} WHERE uuid = %s", params)


def ensure_database_exists() -> None:
    conn = _connect(use_database=False, autocommit=True)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                f"CHARACTER SET {DB_CHARSET} COLLATE {DB_CHARSET}_unicode_ci"
            )
    finally:
        conn.close()


def current_schema_version() -> str | None:
    try:
        row = fetch_one("SELECT value FROM app_meta WHERE `key` = ?", ("schema_version",))
    except pymysql.MySQLError:
        return None
    return row["value"] if row else None


def reset_database() -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            for table_name in RESET_TABLES:
                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
    finally:
        conn.close()
    shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)


def init_database() -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            for statement in SCHEMA_SQL:
                cursor.execute(statement)
            cursor.execute(
                """
                INSERT INTO app_meta (`key`, `value`)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE `value` = VALUES(`value`)
                """,
                ("schema_version", SCHEMA_VERSION),
            )
        conn.commit()
    finally:
        conn.close()


def seed_data() -> None:
    row = fetch_one("SELECT COUNT(*) AS total FROM algorithms")
    if row and row["total"] > 0:
        return

    created_at = now_iso()
    algorithm_uuid = "alg-7f3d91b2-1f0f-4e1c-b123-001"
    version_v1_uuid = "ver-b4e1b301-cb17-44f9-a001-101"
    version_v2_uuid = "ver-a99d1c01-2f17-47f1-b001-102"
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO algorithms (
                    uuid, algorithmCode, algorithmName, algorithmType, framework,
                    runtimeType, languageType, description, status, createdAt, updatedAt
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    algorithm_uuid,
                    "yolo_detector",
                    "YOLO目标检测",
                    "detection",
                    "PyTorch",
                    "GPU",
                    "Python",
                    "基于YOLO的目标检测算法",
                    "ENABLED",
                    created_at,
                    created_at,
                ),
            )
            cursor.executemany(
                """
                INSERT INTO versions (
                    uuid, algorithmUuid, version, versionName, entrypoint,
                    codePath, configPath, changelog, sourceType, localImageName,
                    imagePullPolicy, registryUrl, repositoryName, imageTag,
                    imageDigest, fullImageUri, imageSize, publishStatus, createdAt, updatedAt
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        version_v1_uuid,
                        algorithm_uuid,
                        "1.0.0",
                        "YOLO基础版",
                        "python main.py",
                        "/workspace/yolo/1.0.0",
                        "/configs/yolo.yaml",
                        "初始版本，支持基础目标检测",
                        "local",
                        "yolo-base:v1-gpu",
                        "Never",
                        "registry.example.com",
                        "algo/yolo",
                        "v1-gpu",
                        "sha256:abcd1234",
                        "registry.example.com/algo/yolo:v1-gpu",
                        536870912,
                        "PUBLISHED",
                        created_at,
                        created_at,
                    ),
                    (
                        version_v2_uuid,
                        algorithm_uuid,
                        "1.0.1",
                        "YOLO调试版",
                        "python main.py",
                        "/workspace/yolo/1.0.1",
                        "/configs/yolo_debug.yaml",
                        "新增调试参数和可视化输出",
                        "local",
                        "yolo-base:v1-gpu",
                        "Never",
                        "registry.example.com",
                        "algo/yolo",
                        "v1-gpu",
                        "sha256:abcd1234",
                        "registry.example.com/algo/yolo:v1-gpu",
                        536870912,
                        "PUBLISHED",
                        created_at,
                        created_at,
                    ),
                ],
            )
        conn.commit()
    finally:
        conn.close()


def ensure_database() -> None:
    ensure_database_exists()
    if current_schema_version() != SCHEMA_VERSION:
        reset_database()
        init_database()
    else:
        init_database()
    seed_data()


def parse_deployment(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["env"] = json_loads(item["env"])
    item["resources"] = json_loads(item["resources"])
    return item
