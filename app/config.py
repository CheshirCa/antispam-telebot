from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    database_path: Path
    log_level: str
    web_host: str
    web_port: int


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in the environment or .env")

    return Settings(
        bot_token=token,
        database_path=Path(os.getenv("DATABASE_PATH", "data/antispam.sqlite3")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        web_host=os.getenv("WEB_HOST", "127.0.0.1"),
        web_port=int(os.getenv("WEB_PORT", "9992")),
    )
