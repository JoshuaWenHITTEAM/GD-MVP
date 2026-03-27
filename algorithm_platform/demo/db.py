import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


TZ = timezone(timedelta(hours=8))
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "demo.db"
RUNTIME_ROOT = BASE_DIR / "runtime"
SCHEMA_VERSION = "2026-03-24-clean"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS algorithms (
    uuid TEXT PRIMARY KEY,
    algorithmCode TEXT NOT NULL UNIQUE,
    algorithmName TEXT NOT NULL,
    algorithmType TEXT NOT NULL,
    framework TEXT NOT NULL,
    runtimeType TEXT NOT NULL,
    languageType TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    createdAt TEXT NOT NULL,
    updatedAt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS versions (
    uuid TEXT PRIMARY KEY,
    algorithmUuid TEXT NOT NULL,
    version TEXT NOT NULL,
    versionName TEXT NOT NULL,
    entrypoint TEXT NOT NULL,
    configPath TEXT NOT NULL,
    changelog TEXT NOT NULL,
    publishStatus TEXT NOT NULL,
    createdAt TEXT NOT NULL,
    updatedAt TEXT NOT NULL,
    UNIQUE (algorithmUuid, version),
    FOREIGN KEY (algorithmUuid) REFERENCES algorithms(uuid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS images (
    uuid TEXT PRIMARY KEY,
    algorithmVersionUuid TEXT NOT NULL,
    registryUrl TEXT NOT NULL,
    repositoryName TEXT NOT NULL,
    imageTag TEXT NOT NULL,
    imageDigest TEXT,
    fullImageUri TEXT NOT NULL,
    imageSize INTEGER,
    isAvailable INTEGER NOT NULL,
    createdAt TEXT NOT NULL,
    FOREIGN KEY (algorithmVersionUuid) REFERENCES versions(uuid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS deployments (
    uuid TEXT PRIMARY KEY,
    algorithmVersionUuid TEXT NOT NULL,
    imageUuid TEXT NOT NULL,
    namespace TEXT NOT NULL,
    deploymentName TEXT NOT NULL,
    serviceName TEXT NOT NULL,
    status TEXT NOT NULL,
    port INTEGER NOT NULL,
    replicas INTEGER NOT NULL,
    readyReplicas INTEGER NOT NULL,
    accessEndpoint TEXT NOT NULL,
    errorMessage TEXT NOT NULL,
    env TEXT NOT NULL,
    resources TEXT NOT NULL,
    deployedAt TEXT NOT NULL,
    updatedAt TEXT NOT NULL,
    UNIQUE (namespace, deploymentName),
    FOREIGN KEY (algorithmVersionUuid) REFERENCES versions(uuid),
    FOREIGN KEY (imageUuid) REFERENCES images(uuid)
);

CREATE TABLE IF NOT EXISTS debug_sessions (
    uuid TEXT PRIMARY KEY,
    algorithmUuid TEXT NOT NULL,
    baseVersionUuid TEXT NOT NULL,
    currentVersionUuid TEXT NOT NULL,
    sessionName TEXT NOT NULL,
    namespace TEXT NOT NULL,
    podName TEXT NOT NULL,
    debugStatus TEXT NOT NULL,
    runtimePath TEXT NOT NULL,
    processPid INTEGER,
    lastError TEXT NOT NULL,
    createdAt TEXT NOT NULL,
    updatedAt TEXT NOT NULL,
    FOREIGN KEY (algorithmUuid) REFERENCES algorithms(uuid),
    FOREIGN KEY (baseVersionUuid) REFERENCES versions(uuid),
    FOREIGN KEY (currentVersionUuid) REFERENCES versions(uuid)
);

CREATE TABLE IF NOT EXISTS hot_updates (
    uuid TEXT PRIMARY KEY,
    debugSessionUuid TEXT NOT NULL,
    fromVersionUuid TEXT NOT NULL,
    toVersionUuid TEXT NOT NULL,
    updateType TEXT NOT NULL,
    updateStatus TEXT NOT NULL,
    operator TEXT NOT NULL,
    startedAt TEXT NOT NULL,
    finishedAt TEXT NOT NULL,
    errorMessage TEXT NOT NULL,
    resultSummary TEXT NOT NULL,
    actionLogPath TEXT NOT NULL,
    FOREIGN KEY (debugSessionUuid) REFERENCES debug_sessions(uuid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS containers (
    uuid TEXT PRIMARY KEY,
    algorithmVersionUuid TEXT NOT NULL,
    imageUuid TEXT NOT NULL,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    image TEXT NOT NULL,
    namespace TEXT NOT NULL,
    port INTEGER NOT NULL,
    replicas INTEGER NOT NULL,
    readyReplicas INTEGER NOT NULL,
    env TEXT NOT NULL,
    cpu TEXT,
    memory TEXT,
    deploymentName TEXT NOT NULL,
    serviceName TEXT NOT NULL,
    status TEXT NOT NULL,
    createdAt TEXT NOT NULL,
    updatedAt TEXT NOT NULL,
    UNIQUE (namespace, deploymentName),
    FOREIGN KEY (algorithmVersionUuid) REFERENCES versions(uuid),
    FOREIGN KEY (imageUuid) REFERENCES images(uuid)
);
"""


def now_iso() -> str:
    return datetime.now(TZ).isoformat()


def json_dumps(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, separators=(",", ":"))


def json_loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    return json.loads(value)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def execute(query: str, params: tuple[Any, ...] = ()) -> None:
    with get_conn() as conn:
        conn.execute(query, params)
        conn.commit()


def update_by_uuid(table: str, uuid: str, values: dict[str, Any]) -> None:
    if not values:
        return

    assignments = ", ".join(f"{key} = ?" for key in values)
    params = tuple(values.values()) + (uuid,)
    execute(f"UPDATE {table} SET {assignments} WHERE uuid = ?", params)


def current_schema_version() -> str | None:
    if not DB_PATH.exists():
        return None

    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
    return row[0] if row else None


def reset_database() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)


def init_database() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES ('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        conn.commit()


def seed_data() -> None:
    row = fetch_one("SELECT COUNT(*) AS total FROM algorithms")
    if row and row["total"] > 0:
        return

    created_at = now_iso()
    algorithm_uuid = "alg-7f3d91b2-1f0f-4e1c-b123-001"
    version_v1_uuid = "ver-b4e1b301-cb17-44f9-a001-101"
    version_v2_uuid = "ver-a99d1c01-2f17-47f1-b001-102"
    image_uuid = "img-3e3f9bb1-82c3-45aa-a111-301"

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO algorithms (
                uuid, algorithmCode, algorithmName, algorithmType, framework,
                runtimeType, languageType, description, status, createdAt, updatedAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        conn.executemany(
            """
            INSERT INTO versions (
                uuid, algorithmUuid, version, versionName, entrypoint,
                configPath, changelog, publishStatus, createdAt, updatedAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    version_v1_uuid,
                    algorithm_uuid,
                    "1.0.0",
                    "YOLO基础版",
                    "python main.py",
                    "/configs/yolo.yaml",
                    "初始版本，支持基础目标检测",
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
                    "/configs/yolo_debug.yaml",
                    "新增调试参数和可视化输出",
                    "PUBLISHED",
                    created_at,
                    created_at,
                ),
            ],
        )
        conn.execute(
            """
            INSERT INTO images (
                uuid, algorithmVersionUuid, registryUrl, repositoryName, imageTag,
                imageDigest, fullImageUri, imageSize, isAvailable, createdAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                image_uuid,
                version_v1_uuid,
                "registry.example.com",
                "algo/yolo",
                "v1-gpu",
                "sha256:abcd1234",
                "registry.example.com/algo/yolo:v1-gpu",
                536870912,
                1,
                created_at,
            ),
        )
        conn.commit()


def ensure_database() -> None:
    if current_schema_version() != SCHEMA_VERSION:
        reset_database()
        init_database()
    else:
        init_database()
    seed_data()


def parse_image(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["isAvailable"] = bool(item["isAvailable"])
    return item


def parse_deployment(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["env"] = json_loads(item["env"])
    item["resources"] = json_loads(item["resources"])
    return item


def parse_container(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["env"] = json_loads(item["env"])
    return item
