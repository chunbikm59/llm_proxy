import os

from dotenv import load_dotenv
from sqlalchemy import Column, Float, Integer, Text, create_engine
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


engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Session:
    return SessionLocal()


def init_db():
    Base.metadata.create_all(bind=engine)
