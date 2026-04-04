from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 数据库连接配置
DATABASE_URL = "postgresql://postgres:053542@localhost:5432/algorithm_db"

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

# 测试用例
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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
