from simple_kirolets.config import Settings
from simple_kirolets.github_workflow import GitHubWorkflow


def test_redact_removes_raw_and_encoded_credentials():
    workflow = GitHubWorkflow(
        Settings(
            telegram_bot_token="telegram-token",
            telegram_allowed_user_ids=frozenset(),
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
            yolo=False,
            log_level="INFO",
        )
    )

    redacted = workflow._redact(
        "github-token "
        "eC1hY2Nlc3MtdG9rZW46Z2l0aHViLXRva2Vu "
        "kiro-token"
    )

    assert "github-token" not in redacted
    assert "eC1hY2Nlc3MtdG9rZW46Z2l0aHViLXRva2Vu" not in redacted
    assert "kiro-token" not in redacted


def test_summarize_output_strips_ansi_and_limits_length():
    workflow = GitHubWorkflow(
        Settings(
            telegram_bot_token="telegram-token",
            telegram_allowed_user_ids=frozenset(),
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
            yolo=False,
            log_level="INFO",
        )
    )

    summary = workflow._summarize_output(f"\x1b[38;5;141m{'a' * 1300}\x1b[0m")

    assert "\x1b" not in summary
    assert len(summary) < 1250
    assert summary.endswith("...[truncated]")


def test_extract_usage_report_from_kiro_output():
    workflow = GitHubWorkflow(
        Settings(
            telegram_bot_token="telegram-token",
            telegram_allowed_user_ids=frozenset(),
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
            yolo=False,
            log_level="INFO",
        )
    )

    assert workflow._extract_usage_report("Credits used: 12.5") == "Credits used: 12.5"
    assert workflow._extract_usage_report("Used 1,234 credits") == "Credits used: 1,234"
    assert workflow._extract_usage_report("Tokens used: 987") == "Tokens used: 987"
    assert workflow._extract_usage_report("no usage reported") is None
