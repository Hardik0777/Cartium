from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    kwargs = {"pool_pre_ping": True}  # reconnect cleanly if MySQL closed an idle connection
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
    return create_engine(url, **kwargs)


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_database_if_missing(url: str) -> None:
    """Creates the MySQL database itself (e.g. `cartium`) so first-time setup is one command."""
    parsed = make_url(url)
    if not parsed.drivername.startswith("mysql") or not parsed.database:
        return
    # Connect to the server without selecting a database. (URL.set(database=None) keeps the old
    # value in recent SQLAlchemy versions, so build a fresh URL instead.)
    server_url = URL.create(parsed.drivername, username=parsed.username, password=parsed.password,
                            host=parsed.host, port=parsed.port, query=parsed.query)
    server = create_engine(server_url)
    with server.connect() as conn:
        conn.execute(text(
            f"CREATE DATABASE IF NOT EXISTS `{parsed.database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ))
    server.dispose()
