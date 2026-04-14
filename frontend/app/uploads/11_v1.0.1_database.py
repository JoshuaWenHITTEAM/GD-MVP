from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

# 数据库连接配置
DATABASE_URL = "postgresql://postgres:123456@localhost:5432/algorithm_db"

# 创建引擎
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 测试用例  算法注册表
class AlgorithmModel(Base):
    __tablename__ = "algorithms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(32), nullable=False)
    version = Column(String(20), nullable=False)
    algorithm_type = Column(String(50), nullable=False)
    tags = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    auth = Column(String(20), nullable=False, default="公开")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    file_path = Column(String(255), nullable=True)  # 存储上传文件的路径
    versions = relationship("AlgorithmVersionModel", back_populates="algorithm", cascade="all, delete-orphan")

# 算法版本表
class AlgorithmVersionModel(Base):
    __tablename__ = "algorithm_versions"

    id = Column(Integer, primary_key=True, index=True)
    algorithm_id = Column(Integer, ForeignKey("algorithms.id"), nullable=False)
    version_number = Column(String(50), nullable=False)          # 用户自定义或自动生成的版本号
    file_path = Column(String(255), nullable=False)              # 上传文件的存储路径
    rule_used = Column(String(50), nullable=True)                # 使用的校验规则（可选）
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    algorithm = relationship("AlgorithmModel", back_populates="versions")          # 与 AlgorithmModel 的关联关系（可选，便于 ORM 查询）


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
