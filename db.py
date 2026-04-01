import os

from dotenv import load_dotenv
from sqlalchemy import Column, Float, Integer, Text, create_engine
from sqlalchemy.types import JSON
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

DATABASE_URL = os.environ["PROXY_DATABASE_URL"]


class Base(DeclarativeBase):
    pass


class ApiKey(Base):
    __tablename__ = "api_keys"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    key            = Column(Text, unique=True, nullable=False)
    name           = Column(Text, nullable=False)
    description    = Column(Text, nullable=False, default="")
    created_at     = Column(Text, nullable=False)
    is_active      = Column(Integer, nullable=False, default=1)
    total_requests = Column(Integer, nullable=False, default=0)
    total_tokens   = Column(Integer, nullable=False, default=0)
    total_cost_usd = Column(Float, nullable=False, default=0.0)


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    api_key       = Column(Text, nullable=False, index=True)
    model         = Column(Text, nullable=False)
    request_type  = Column(Text, nullable=False, default="chat")
    date          = Column(Text, nullable=False, index=True)
    input_tokens  = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens  = Column(Integer, nullable=False, default=0)
    cost_usd      = Column(Float, nullable=False, default=0.0)
    created_at    = Column(Text, nullable=False)


class LlamaCppInstance(Base):
    __tablename__ = "llama_instances"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    name                 = Column(Text, unique=True, nullable=False)
    executable_path      = Column(Text, nullable=False)
    model_path           = Column(Text, nullable=False)
    host                 = Column(Text, nullable=False, default="127.0.0.1")
    port                 = Column(Integer, nullable=False)
    context_size         = Column(Integer, nullable=False, default=4096)
    n_threads            = Column(Integer, nullable=True)
    n_gpu_layers         = Column(Integer, nullable=False, default=0)
    parallel             = Column(Integer, nullable=False, default=1)
    batch_size           = Column(Integer, nullable=False, default=512)
    split_mode           = Column(Text, nullable=True)
    defrag_thold         = Column(Float, nullable=True)
    cache_type_k         = Column(Text, nullable=True)
    cache_type_v         = Column(Text, nullable=True)
    flash_attn           = Column(Integer, nullable=False, default=0)
    cont_batching        = Column(Integer, nullable=False, default=0)
    no_webui             = Column(Integer, nullable=False, default=1)
    extra_args           = Column(JSON, nullable=False, default=list)
    auto_start           = Column(Integer, nullable=False, default=1)
    auto_restart         = Column(Integer, nullable=False, default=0)
    max_restart_attempts = Column(Integer, nullable=False, default=3)
    startup_timeout      = Column(Integer, nullable=False, default=120)
    is_active            = Column(Integer, nullable=False, default=1)
    created_at           = Column(Text, nullable=False)
    updated_at           = Column(Text, nullable=False)


engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Session:
    return SessionLocal()


def init_db():
    Base.metadata.create_all(bind=engine)
