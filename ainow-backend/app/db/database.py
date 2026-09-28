from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


engine = create_engine(
    settings.database_url,
    echo=False,
    # psycopg (v3) auto-upgrades repeated queries to server-side
    # prepared statements. That breaks through a transaction-mode
    # pooler (Supabase's "Transaction pooler", PgBouncer in the
    # same mode): each request can land on a different backend
    # connection than the one a statement was prepared on, so a
    # name can collide with an unrelated session's statement —
    # "prepared statement ... already exists". Harmless to
    # disable on a direct connection too.
    connect_args={"prepare_threshold": None},
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()