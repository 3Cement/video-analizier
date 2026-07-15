from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def configure_engine(database_url: str | None = None, **kwargs) -> Engine:
    global engine, SessionLocal
    settings = get_settings()
    url = database_url or settings.database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, **kwargs)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine


def get_engine() -> Engine:
    if engine is None:
        configure_engine()
    assert engine is not None
    return engine


def _sqlite_add_column_if_missing(engine: Engine, table: str, column: str, ddl: str) -> None:
    if not str(engine.url).startswith("sqlite"):
        return
    with engine.begin() as conn:
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        existing = {row[1] for row in rows}
        if column not in existing:
            conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def migrate_schema() -> None:
    engine = get_engine()
    _sqlite_add_column_if_missing(engine, "sources", "user_id", "user_id VARCHAR(128) DEFAULT 'anonymous'")
    _sqlite_add_column_if_missing(engine, "sources", "video_id", "video_id VARCHAR(32)")
    _sqlite_add_column_if_missing(engine, "sources", "error_code", "error_code VARCHAR(64)")
    _sqlite_add_column_if_missing(engine, "sources", "error_hint", "error_hint TEXT")


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
    migrate_schema()


def get_session() -> Session:
    if SessionLocal is None:
        configure_engine()
    assert SessionLocal is not None
    return SessionLocal()


def get_db() -> Generator[Session, None, None]:
    db = get_session()
    try:
        yield db
    finally:
        db.close()