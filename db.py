from sqlalchemy import Column, Float, Integer, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DB_PATH = "proxy.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"


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


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _set_pragma(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Session:
    return SessionLocal()


def init_db():
    Base.metadata.create_all(bind=engine)
