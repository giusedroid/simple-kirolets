from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_allowed_user_ids: frozenset[int]
    github_repository_url: str
    github_token: str
    github_username: str
    github_email: str
    github_base_branch: str
    git_cache_dir: str
    kiro_api_key: str
    kiro_trust_tools: str
    kiro_timeout_seconds: int
    progress_update_interval_seconds: int
    yolo: bool
    log_level: str = "INFO"


def load_settings() -> Settings:
    load_dotenv()

    return Settings(
        telegram_bot_token=_required_env("TELEGRAM_BOT_TOKEN"),
        telegram_allowed_user_ids=_int_set_env("TELEGRAM_ALLOWED_USER_IDS"),
        github_repository_url=_required_env("GITHUB_REPOSITORY_URL"),
        github_token=_required_env("GITHUB_TOKEN"),
        github_username=_required_env("GITHUB_USERNAME"),
        github_email=_required_env("GITHUB_EMAIL"),
        github_base_branch=os.getenv("GITHUB_BASE_BRANCH", "main").strip() or "main",
        git_cache_dir=os.getenv("GIT_CACHE_DIR", "").strip() or ".simple-kirolets/git-cache",
        kiro_api_key=_required_env("KIRO_API_KEY"),
        kiro_trust_tools=os.getenv("KIRO_TRUST_TOOLS", "read,grep,write,bash").strip()
        or "read,grep,write,bash",
        kiro_timeout_seconds=_int_env("KIRO_TIMEOUT_SECONDS", 1800),
        progress_update_interval_seconds=_int_env("PROGRESS_UPDATE_INTERVAL_SECONDS", 30),
        yolo=_bool_env("YOLO"),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
    )


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required. Copy .env.example to .env and set it.")

    return value


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


def _bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name, "").strip().lower()
    if not raw_value:
        return default

    if raw_value in {"1", "true", "yes", "y", "on"}:
        return True

    if raw_value in {"0", "false", "no", "n", "off"}:
        return False

    raise RuntimeError(f"{name} must be a boolean.")


def _int_set_env(name: str) -> frozenset[int]:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return frozenset()

    values: set[int] = set()
    for item in raw_value.split(","):
        item = item.strip()
        if not item:
            continue

        try:
            values.add(int(item))
        except ValueError as exc:
            raise RuntimeError(f"{name} must contain comma-separated integer IDs.") from exc

    return frozenset(values)
