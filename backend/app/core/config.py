"""Application settings, read from environment variables (and a local .env file)."""
import logging
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"
logger = logging.getLogger(__name__)


def _load_env_file() -> None:
    """Minimal .env loader. Real environment variables always win."""
    if not ENV_FILE.exists():
        return
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.split(" #", 1)[0].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _list(name: str, default: str) -> list[str]:
    return [item.strip().rstrip("/") for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").lower()
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "NEON//CORE")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = _int("ACCESS_TOKEN_EXPIRE_MINUTES", 1440)
    FRONTEND_ORIGINS: list[str] = field(default_factory=lambda: _list("FRONTEND_ORIGINS", "http://localhost:5173"))

    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "neon_core")
    LOG_RETENTION_DAYS: int = _int("LOG_RETENTION_DAYS", 90)

    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openrouter/free")
    AI_COOLDOWN_SECONDS: int = _int("AI_COOLDOWN_SECONDS", 10)
    AI_TIMEOUT_SECONDS: int = _int("AI_TIMEOUT_SECONDS", 60)

    # Chat limits
    MAX_MESSAGE_LENGTH: int = 2000
    RATE_LIMIT_MESSAGES: int = _int("RATE_LIMIT_MESSAGES", 8)  # max messages ...
    RATE_LIMIT_WINDOW_SECONDS: int = _int("RATE_LIMIT_WINDOW_SECONDS", 10)  # ... per this many seconds

    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()

# Never run production with a missing or weak signing key.
if len(settings.SECRET_KEY) < 32:
    if settings.is_production:
        raise RuntimeError("SECRET_KEY must be a random string of at least 32 characters in production.")
    object.__setattr__(settings, "SECRET_KEY", secrets.token_urlsafe(48))
    logger.warning("SECRET_KEY not set: using a temporary key (everyone is logged out when the server restarts).")
