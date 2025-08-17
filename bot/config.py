import os
from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()


DEFAULT_TELEGRAM_TOKEN = "6726781810:AAG3TQxVdGQUf8J9yG0LmklCsQw6m4mdvj4"


@dataclass
class BotConfig:
    telegram_token: str


def load_config() -> BotConfig:
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if not token:
        token = DEFAULT_TELEGRAM_TOKEN
        # Deliberately not logging the token value
        print("[config] Using default token from configuration. Set TELEGRAM_TOKEN to override.")
    return BotConfig(telegram_token=token)