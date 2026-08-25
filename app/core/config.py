import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

# Load a simple .env file without requiring a separate runtime tool.
if ENV_FILE.exists():
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def normalize_database_url(value: str) -> str:
    if value.startswith("sqlite:///"):
        path_text = value[len("sqlite:///"):]
        path = Path(path_text)
        if not path.is_absolute():
            path = BASE_DIR / path
        return f"sqlite:///{path.as_posix()}"
    return value


@dataclass(frozen=True)
class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "AI Chat Engine")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_ME_IN_ENV")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    DATABASE_URL: str = normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///./chat.db"))
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openrouter/free")
    ALLOW_ORIGINS: str = os.getenv("ALLOW_ORIGINS", "*")
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "neon_core")


settings = Settings()
