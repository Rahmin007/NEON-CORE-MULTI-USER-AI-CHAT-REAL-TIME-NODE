from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    # Import every model before create_all so all tables are registered on Base.metadata.
    from app.models import ChatMessage, User  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Lightweight development migration for existing SQLite databases.
    # create_all() does not add new columns to an existing table.
    if settings.DATABASE_URL.startswith("sqlite"):
        with engine.begin() as conn:
            columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()}
            if "muted_until" not in columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN muted_until DATETIME")

    # Fail fast with a useful message instead of letting registration produce a vague 500.
    required = {"users", "chat_messages"}
    actual = set(inspect(engine).get_table_names())
    missing = required - actual
    if missing:
        raise RuntimeError(
            f"Database initialization failed. Missing tables: {', '.join(sorted(missing))}. "
            f"Database URL: {settings.DATABASE_URL}"
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
