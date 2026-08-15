from __future__ import annotations
import os
from typing import Any, Dict, Generator, Optional
import uuid as py_uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, create_engine, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker
import pymysql      

MYSQL_USER = os.getenv("MYSQL_USER", "appuser")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE_URL = os.getenv(
    "MYSQL_DATABASE_URL",
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@localhost:3306/algo_manager",
)

POSTGRES_DATABASE_URL = os.getenv(
    "POSTGRES_DATABASE_URL",
    "postgresql://appuser:@localhost:5432/mediadb",
)

# 创建 MySQL 引擎
mysql_engine = create_engine(
    MYSQL_DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False
)
MySQLSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=mysql_engine)
Base = declarative_base()

PostgresBase = declarative_base()

postgres_engine = None
PostgresSessionLocal = None
if POSTGRES_DATABASE_URL:
    postgres_engine = create_engine(
        POSTGRES_DATABASE_URL,
        pool_pre_ping=True,
        echo=False,
    )
    PostgresSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=postgres_engine)

## 算法注册表
class AlgorithmModel(Base):
    __tablename__ = "algorithms"

    # 原：uuid = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(64), primary_key=True)
    
    # 新增：对应 SQL 中的 algorithmCode
    algorithmCode = Column(String(64), nullable=False, unique=True)
    
    # 原：name = Column(String(32), nullable=False)
    algorithmName = Column(String(128), nullable=False)
    
    # 原：algorithm_type = Column(String(50), nullable=False)
    algorithmType = Column(String(64), nullable=False)
    
    # 新增字段
    framework = Column(String(64), nullable=False)
    runtimeType = Column(String(32), nullable=False)
    languageType = Column(String(32), nullable=False)
    
    # 原：file_path = Column(String(255), nullable=True) -> 分解为 codePath 和 configPath
    codePath = Column(String(255), nullable=False)
    configPath = Column(String(255), nullable=False)
    
    # 原：description = Column(Text, nullable=True)
    description = Column(Text, nullable=False) # SQL中是 NOT NULL
    
    # 新增：状态字段
    status = Column(String(32), nullable=False)
    
    # 原：created_at / updated_at 修改为驼峰并匹配精确度
    createdAt = Column(DateTime, nullable=False, default=datetime.utcnow)
    updatedAt = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系映射
    versions = relationship("AlgorithmVersionModel", back_populates="algorithm", cascade="all, delete-orphan")

    # 以下为 SQL 中不存在、被移除的字段（注释备份）：
    # version = Column(String(20)) # SQL 中算法表不存版本，版本在 versions 表
    # tags = Column(String(100))    # SQL 中无此字段
    # auth = Column(String(20))    # SQL 中无此字段


# 算法版本表
class AlgorithmVersionModel(Base):
    # 原：__tablename__ = "algorithm_versions"
    __tablename__ = "versions"

    # 原：uuid = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(64), primary_key=True)
    
    # 原：algorithm_id = Column(Integer, ForeignKey("algorithms.id"), nullable=False)
    algorithmUuid = Column(String(64), ForeignKey("algorithms.uuid", ondelete="CASCADE"), nullable=False)
    
    # 原：version_number = Column(String(50), nullable=False)
    version = Column(String(64), nullable=False)
    
    # 新增字段
    versionName = Column(String(128), nullable=False)
    entrypoint = Column(String(255), nullable=False)
    sourceRevision = Column(String(255), nullable=True)
    configRevision = Column(String(255), nullable=True)
    changelog = Column(Text, nullable=False)
    sourceType = Column(String(32), nullable=False)
    
    # 镜像相关字段（新增）
    localImageName = Column(String(255), nullable=False)
    imagePullPolicy = Column(String(32), nullable=False)
    registryUrl = Column(String(255), nullable=False)
    repositoryName = Column(String(255), nullable=False)
    imageTag = Column(String(128), nullable=False)
    imageDigest = Column(String(255), nullable=True)
    fullImageUri = Column(String(512), nullable=False)
    imageSize = Column(BigInteger, nullable=True)
    
    # 状态与逻辑删除
    publishStatus = Column(String(32), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False) # 对应 TINYINT(1)
    
    # 时间字段修改
    createdAt = Column(DateTime, nullable=False, default=datetime.utcnow)
    updatedAt = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 联合唯一索引：UNIQUE KEY uniq_algorithm_version (algorithmUuid, version)
    __table_args__ = (
        UniqueConstraint('algorithmUuid', 'version', name='uniq_algorithm_version'),
    )

    # 关系映射
    algorithm = relationship("AlgorithmModel", back_populates="versions")

    # 以下为 SQL 中不存在、被移除的字段（注释备份）：
    # file_path = Column(String(255)) # 已被具体的镜像/路径字段替代
    # rule_used = Column(String(50))  # SQL 中无此字段
class MediaAsset(PostgresBase):
    __tablename__ = 'media_asset'
    __table_args__ = (
        UniqueConstraint('bucket_name', 'object_key', name='uq_media_asset_bucket_object'),
        Index('idx_media_asset_uuid', 'uuid', unique=True),
        Index('idx_media_asset_dataset_name', 'dataset_name'),
        Index('idx_media_asset_media_type', 'media_type'),
        Index('idx_media_asset_status', 'status'),
        Index('idx_media_asset_split', 'split'),
        Index('idx_media_asset_sequence_name', 'sequence_name'),
        Index('idx_media_asset_modality', 'modality'),
        Index('idx_media_asset_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    uuid: Mapped[py_uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        unique=True,
        server_default=text('gen_random_uuid()'),
    )

    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    bucket_name: Mapped[str] = mapped_column(String(128), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)

    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    etag: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'active'"))

    dataset_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    split: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sequence_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    modality: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    previewable: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    source_results: Mapped[list['AlgorithmResult']] = relationship(
        back_populates='source_asset',
        foreign_keys='AlgorithmResult.source_asset_id',
    )
    generated_results: Mapped[list['AlgorithmResult']] = relationship(
        back_populates='result_asset',
        foreign_keys='AlgorithmResult.result_asset_id',
    )


class AlgorithmResult(PostgresBase):
    __tablename__ = 'algorithm_result'
    __table_args__ = (
        Index('idx_algorithm_result_uuid', 'uuid', unique=True),
        Index('idx_algorithm_result_source_asset_id', 'source_asset_id'),
        Index('idx_algorithm_result_result_asset_id', 'result_asset_id'),
        Index('idx_algorithm_result_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    uuid: Mapped[py_uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        unique=True,
        server_default=text('gen_random_uuid()'),
    )

    source_asset_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey('media_asset.id', ondelete='CASCADE'),
        nullable=False,
    )
    result_asset_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey('media_asset.id', ondelete='CASCADE'),
        nullable=False,
    )
    result_type: Mapped[str] = mapped_column(String(128), nullable=False)
    metrics: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    extra: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    source_asset: Mapped[MediaAsset] = relationship(
        back_populates='source_results',
        foreign_keys=[source_asset_id],
    )
    result_asset: Mapped[MediaAsset] = relationship(
        back_populates='generated_results',
        foreign_keys=[result_asset_id],
    )



def get_db() -> Generator:
    db = MySQLSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_postgres_db() -> Generator:
    if PostgresSessionLocal is None:
        raise RuntimeError('POSTGRES_DATABASE_URL is not configured')
    db = PostgresSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=mysql_engine)
    if postgres_engine is not None:
        PostgresBase.metadata.create_all(bind=postgres_engine)
