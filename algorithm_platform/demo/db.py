import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymysql


TZ = timezone(timedelta(hours=8))
BASE_DIR = Path(__file__).resolve().parent
RUNTIME_ROOT = BASE_DIR / "runtime"
SCHEMA_VERSION = "2026-04-21-algorithm-paths"

DB_HOST = os.getenv("DEMO_DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DEMO_DB_PORT", "3307"))
DB_USER = os.getenv("DEMO_DB_USER", "root")
DB_PASSWORD = os.getenv("DEMO_DB_PASSWORD", "123456")
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
        codePath VARCHAR(255) NOT NULL,
        configPath VARCHAR(255) NOT NULL,
        description TEXT NOT NULL,
        status VARCHAR(32) NOT NULL,
        createdAt DATETIME(6) NOT NULL,
        updatedAt DATETIME(6) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS versions (
        uuid VARCHAR(64) PRIMARY KEY,
        algorithmUuid VARCHAR(64) NOT NULL,
        version VARCHAR(64) NOT NULL,
        versionName VARCHAR(128) NOT NULL,
        entrypoint VARCHAR(255) NOT NULL,
        sourceRevision VARCHAR(255) NULL,
        configRevision VARCHAR(255) NULL,
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
        is_deleted TINYINT(1) NOT NULL DEFAULT 0,
        createdAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
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

        
        is_deleted TINYINT(1) NOT NULL DEFAULT 0,
        active_flag TINYINT(1) DEFAULT 1,
        
        deployedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        
        UNIQUE KEY uniq_namespace_deployment (namespace, deploymentName, active_flag),
        KEY idx_deployments_version_uuid (versionUuid),
        KEY idx_deployments_status (status),
        KEY idx_deployments_namespace (namespace),
        KEY idx_deployments_is_deleted (is_deleted),

        CONSTRAINT fk_deployments_version
        FOREIGN KEY (versionUuid) REFERENCES versions(uuid)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
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
        startedAt DATETIME(6) NOT NULL,
        finishedAt DATETIME(6) NULL,
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


def now_db() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


def json_dumps(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, separators=(",", ":"))


def json_loads(value: Optional[str]) -> Dict[str, Any]:
    if not value:
        return {}
    return json.loads(value)


def _normalize_query(query: str) -> str:
    return query.replace("?", "%s")


def to_db_datetime(value: Optional[Any]) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone(TZ)
    return dt.replace(tzinfo=None)


def _to_api_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.replace(tzinfo=TZ).isoformat()
    return value


def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _to_api_value(value) for key, value in row.items()}


def _connect(*, use_database: bool = True, autocommit: bool = False) -> pymysql.connections.Connection:
    params: Dict[str, Any] = {
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


def fetch_one(query: str, params: Tuple[Any, ...] = ()) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(_normalize_query(query), params)
            row = cursor.fetchone()
        return _normalize_row(dict(row)) if row else None
    finally:
        conn.close()


def fetch_all(query: str, params: Tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(_normalize_query(query), params)
            rows = cursor.fetchall()
        return [_normalize_row(dict(row)) for row in rows]
    finally:
        conn.close()


def execute(query: str, params: Tuple[Any, ...] = ()) -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(_normalize_query(query), params)
        conn.commit()
    finally:
        conn.close()


def update_by_uuid(table: str, uuid: str, values: Dict[str, Any]) -> None:
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


def current_schema_version() -> Optional[str]:
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

    created_at = now_db()
    algorithm_uuid = "alg-7f3d91b2-1f0f-4e1c-b123-001"
    version_v1_uuid = "ver-b4e1b301-cb17-44f9-a001-101"
    version_v2_uuid = "ver-a99d1c01-2f17-47f1-b001-102"

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 插入算法
            cursor.execute(
                """
                INSERT INTO algorithms (
                    uuid, algorithmCode, algorithmName, algorithmType, framework,
                    runtimeType, languageType, codePath, configPath, description,
                    status, createdAt, updatedAt
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    algorithm_uuid,
                    "yolo_detector",
                    "YOLO目标检测",
                    "detection",
                    "PyTorch",
                    "GPU",
                    "Python",
                    "/workspace/yolo",
                    "/configs/yolo/default",
                    "基于YOLO的目标检测算法",
                    "ENABLED",
                    created_at,
                    created_at,
                ),
            )

            # 插入版本（重点：带 is_deleted）
            cursor.executemany(
                """
                INSERT INTO versions (
                    uuid, algorithmUuid, version, versionName, entrypoint,
                    sourceRevision, configRevision, changelog, sourceType, localImageName,
                    imagePullPolicy, registryUrl, repositoryName, imageTag,
                    imageDigest, fullImageUri, imageSize, publishStatus,
                    is_deleted, createdAt, updatedAt
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        version_v1_uuid,
                        algorithm_uuid,
                        "1.0.0",
                        "YOLO基础版",
                        "python main.py",
                        "git:main@abc1234",
                        "config:v1",
                        "初始版本，支持基础目标检测",
                        "local",
                        "gd-docker-preprocess:v1",   # 建议本地镜像
                        "IfNotPresent",
                        "",
                        "gd-docker-preprocess",
                        "v1",
                        "",
                        "gd-docker-preprocess:v1",
                        536870912,
                        "PUBLISHED",
                        0,
                        created_at,
                        created_at,
                    ),
                    (
                        version_v2_uuid,
                        algorithm_uuid,
                        "1.0.1",
                        "YOLO调试版",
                        "python main.py",
                        "git:main@bcd2345",
                        "config:v2",
                        "新增调试参数和可视化输出",
                        "local",
                        "gd-docker-preprocess:v2",
                        "IfNotPresent",
                        "",
                        "gd-docker-preprocess",
                        "v2",
                        "",
                        "gd-docker-preprocess:v2",
                        536870912,
                        "PUBLISHED",
                        0,
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


def parse_deployment(row: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(row)
    item["env"] = json_loads(item["env"])
    item["resources"] = json_loads(item["resources"])
    return item
