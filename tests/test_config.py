import pytest

from simple_kirolets.config import Settings, load_settings


def test_load_settings_reads_values(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-token")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "123, 456")
    monkeypatch.setenv("GITHUB_REPOSITORY_URL", "https://github.com/example/repo.git")
    monkeypatch.setenv("GITHUB_TOKEN", "github-token")
    monkeypatch.setenv("GITHUB_USERNAME", "octocat")
    monkeypatch.setenv("GITHUB_EMAIL", "octocat@example.com")
    monkeypatch.setenv("KIRO_API_KEY", "kiro-token")
    monkeypatch.setenv("YOLO", "true")

    assert load_settings() == Settings(
        telegram_bot_token="telegram-token",
        telegram_allowed_user_ids=frozenset({123, 456}),
        github_repository_url="https://github.com/example/repo.git",
        github_token="github-token",
        github_username="octocat",
        github_email="octocat@example.com",
        github_base_branch="main",
        git_cache_dir=".simple-kirolets/git-cache",
        kiro_api_key="kiro-token",
        kiro_trust_tools="read,grep,write,bash",
        kiro_timeout_seconds=1800,
        progress_update_interval_seconds=30,
        yolo=True,
        log_level="INFO",
    )


def test_load_settings_requires_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN is required"):
        load_settings()
