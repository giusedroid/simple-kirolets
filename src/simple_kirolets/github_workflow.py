import asyncio
import base64
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
import re
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from simple_kirolets.config import Settings


@dataclass(frozen=True)
class WorkflowResult:
    branch_name: str
    pr_url: str | None
    pushed_to_base: bool
    changed: bool
    kiro_response: str
    usage_report: str | None


@dataclass(frozen=True)
class PullRequestDescription:
    title: str
    body: str


class WorkflowError(RuntimeError):
    pass


class GitHubWorkflow:
    _cache_locks: dict[str, asyncio.Lock] = {}

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def execute(self, request_text: str, user_label: str) -> WorkflowResult:
        async with _temporary_directory() as workspace:
            repo_dir = os.path.join(workspace, "repo")
            response_path = os.path.join(workspace, "kiro-response.md")
            branch_name = self._branch_name(user_label)
            bare_repo_dir = await self._prepare_bare_repo_cache()

            await self._git(
                "--git-dir",
                bare_repo_dir,
                "worktree",
                "add",
                "-b",
                branch_name,
                repo_dir,
                self._base_ref(),
                cwd=workspace,
            )

            try:
                kiro_output = await self._run_kiro(repo_dir, request_text, response_path)
                kiro_response = await self._read_kiro_response(response_path, kiro_output)
                usage_report = self._extract_usage_report(kiro_output)
                changed = await self._has_changes(repo_dir)

                if not changed:
                    return WorkflowResult(
                        branch_name=branch_name,
                        pr_url=None,
                        pushed_to_base=False,
                        changed=False,
                        kiro_response=kiro_response,
                        usage_report=usage_report,
                    )

                await self._git("add", "-A", cwd=repo_dir)
                await self._configure_git_identity(repo_dir)
                await self._git("commit", "-m", self._commit_message(request_text), cwd=repo_dir)

                if self._settings.yolo:
                    await self._git_authenticated(
                        "push",
                        "origin",
                        f"HEAD:{self._settings.github_base_branch}",
                        cwd=repo_dir,
                    )
                    return WorkflowResult(
                        branch_name=branch_name,
                        pr_url=None,
                        pushed_to_base=True,
                        changed=True,
                        kiro_response=kiro_response,
                        usage_report=usage_report,
                    )

                pr_description = await self._generate_pull_request_description(
                    repo_dir,
                    branch_name,
                    request_text,
                    kiro_output,
                )
                await self._git_authenticated("push", "-u", "origin", branch_name, cwd=repo_dir)
                pr_url = await self._create_pull_request(branch_name, pr_description)

                return WorkflowResult(
                    branch_name=branch_name,
                    pr_url=pr_url,
                    pushed_to_base=False,
                    changed=True,
                    kiro_response=kiro_response,
                    usage_report=usage_report,
                )
            finally:
                await self._remove_worktree(bare_repo_dir, repo_dir)

    async def _prepare_bare_repo_cache(self) -> str:
        os.makedirs(self._settings.git_cache_dir, exist_ok=True)
        bare_repo_dir = self._bare_repo_dir()
        lock = self._cache_locks.setdefault(bare_repo_dir, asyncio.Lock())

        async with lock:
            if os.path.exists(bare_repo_dir):
                await self._git(
                    "--git-dir",
                    bare_repo_dir,
                    "remote",
                    "set-url",
                    "origin",
                    self._settings.github_repository_url,
                    cwd=self._settings.git_cache_dir,
                )
                await self._git_authenticated(
                    "--git-dir",
                    bare_repo_dir,
                    "fetch",
                    "origin",
                    "--prune",
                    cwd=bare_repo_dir,
                )
                await self._git("--git-dir", bare_repo_dir, "worktree", "prune", cwd=bare_repo_dir)
            else:
                await self._git_authenticated(
                    "clone",
                    "--bare",
                    self._settings.github_repository_url,
                    bare_repo_dir,
                    cwd=self._settings.git_cache_dir,
                )

        return bare_repo_dir

    async def _remove_worktree(self, bare_repo_dir: str, repo_dir: str) -> None:
        await self._best_effort_git(
            "--git-dir",
            bare_repo_dir,
            "worktree",
            "remove",
            "--force",
            repo_dir,
            cwd=os.path.dirname(repo_dir),
        )
        await self._best_effort_git(
            "--git-dir",
            bare_repo_dir,
            "worktree",
            "prune",
            cwd=os.path.dirname(repo_dir),
        )

    async def _best_effort_git(self, *args: str, cwd: str) -> None:
        try:
            await self._git(*args, cwd=cwd)
        except WorkflowError:
            return

    async def _run_kiro(
        self,
        repo_dir: str,
        prompt: str,
        response_path: str | None = None,
    ) -> str:
        env = os.environ.copy()
        env["KIRO_API_KEY"] = self._settings.kiro_api_key
        env["NO_COLOR"] = "1"
        env["TERM"] = "dumb"

        return await self._run_command(
            "kiro-cli",
            "chat",
            "--no-interactive",
            f"--trust-tools={self._settings.kiro_trust_tools}",
            self._kiro_prompt(prompt, response_path),
            cwd=repo_dir,
            env=env,
            timeout=self._settings.kiro_timeout_seconds,
        )

    async def _read_kiro_response(self, response_path: str, kiro_output: str) -> str:
        try:
            with open(response_path, encoding="utf-8") as response_file:
                response = response_file.read()
        except OSError:
            return self._summarize_output(kiro_output)

        return self._summarize_output(response)

    async def _generate_pull_request_description(
        self,
        repo_dir: str,
        branch_name: str,
        request_text: str,
        kiro_output: str,
    ) -> PullRequestDescription:
        git_log = await self._git(
            "log",
            "--oneline",
            f"{self._base_ref()}..HEAD",
            cwd=repo_dir,
        )
        git_diff = await self._git(
            "diff",
            "--stat",
            f"{self._base_ref()}..HEAD",
            cwd=repo_dir,
        )
        prompt = self._pr_description_prompt(request_text, git_log, git_diff, kiro_output)

        try:
            kiro_description = await self._run_kiro(repo_dir, prompt)
            return self._parse_pull_request_description(kiro_description)
        except WorkflowError:
            return PullRequestDescription(
                title=self._pr_title(request_text),
                body=self._pr_body(request_text, branch_name, kiro_output),
            )

    async def _has_changes(self, repo_dir: str) -> bool:
        output = await self._git("status", "--porcelain", cwd=repo_dir)
        return bool(output.strip())

    async def _configure_git_identity(self, repo_dir: str) -> None:
        await self._git("config", "user.name", self._settings.github_username, cwd=repo_dir)
        await self._git("config", "user.email", self._settings.github_email, cwd=repo_dir)

    async def _git(self, *args: str, cwd: str) -> str:
        return await self._run_command("git", *args, cwd=cwd, timeout=300)

    async def _git_authenticated(self, *args: str, cwd: str) -> str:
        return await self._run_command(
            "git",
            "-c",
            f"http.https://github.com/.extraheader={self._github_auth_header()}",
            *args,
            cwd=cwd,
            timeout=300,
        )

    async def _run_command(
        self,
        *args: str,
        cwd: str,
        env: dict[str, str] | None = None,
        timeout: int,
    ) -> str:
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise WorkflowError(f"Command timed out: {args[0]}") from exc

        output = (stdout + stderr).decode("utf-8", errors="replace")
        if process.returncode != 0:
            raise WorkflowError(self._redact(f"Command failed: {' '.join(args)}\n{output}"))

        return self._redact(output)

    async def _create_pull_request(
        self,
        branch_name: str,
        pr_description: PullRequestDescription,
    ) -> str:
        owner, repo = self._repository_owner_and_name()
        body = {
            "title": pr_description.title,
            "head": branch_name,
            "base": self._settings.github_base_branch,
            "body": pr_description.body,
            "draft": False,
            "maintainer_can_modify": True,
        }

        request = Request(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._settings.github_token}",
                "Content-Type": "application/json",
                "User-Agent": "simple-kirolets",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="POST",
        )

        try:
            response_body = await asyncio.to_thread(self._open_json_request, request)
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise WorkflowError(f"Failed to create PR: {exc.code} {error_body}") from exc

        return response_body["html_url"]

    def _open_json_request(self, request: Request) -> dict:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _bare_repo_dir(self) -> str:
        owner, repo = self._repository_owner_and_name()
        digest = hashlib.sha256(self._settings.github_repository_url.encode("utf-8")).hexdigest()[:12]
        return os.path.abspath(os.path.join(self._settings.git_cache_dir, f"{owner}-{repo}-{digest}.git"))

    def _repository_owner_and_name(self) -> tuple[str, str]:
        parsed = urlparse(self._settings.github_repository_url)
        if parsed.scheme != "https":
            raise WorkflowError("GITHUB_REPOSITORY_URL must be an HTTPS GitHub URL.")

        path_parts = parsed.path.strip("/").removesuffix(".git").split("/")
        if len(path_parts) != 2:
            raise WorkflowError("GITHUB_REPOSITORY_URL must look like https://github.com/owner/repo.git")

        return path_parts[0], path_parts[1]

    def _branch_name(self, user_label: str) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        safe_user = re.sub(r"[^a-zA-Z0-9._-]+", "-", user_label).strip("-") or "user"
        return f"simple-kirolets/{safe_user}/{timestamp}"

    def _commit_message(self, request_text: str) -> str:
        return f"Simple Kirolets: {self._short_text(request_text, 60)}"

    def _pr_title(self, request_text: str) -> str:
        return f"Simple Kirolets: {self._short_text(request_text, 80)}"

    def _pr_body(self, request_text: str, branch_name: str, kiro_output: str) -> str:
        summary = self._summarize_output(kiro_output)
        return (
            "## Request\n\n"
            f"{request_text}\n\n"
            "## Branch\n\n"
            f"`{branch_name}`\n\n"
            "## Kiro Output Summary\n\n"
            f"```text\n{summary}\n```\n"
        )

    def _pr_description_prompt(
        self,
        request_text: str,
        git_log: str,
        git_diff: str,
        kiro_output: str,
    ) -> str:
        return (
            "Prepare a GitHub pull request title and description for the work just completed.\n\n"
            "Use the user's original request, the commit log, and the diff stat. Be concise, "
            "specific, and review-oriented. Do not invent tests or outcomes that are not present.\n\n"
            "Return exactly this format:\n"
            "TITLE: <one-line PR title>\n"
            "BODY:\n"
            "## Summary\n"
            "- <bullet>\n\n"
            "## Validation\n"
            "- <bullet or 'Not run'>\n\n"
            f"USER REQUEST:\n{request_text}\n\n"
            f"GIT LOG:\n{self._truncate_for_prompt(git_log)}\n\n"
            f"DIFF STAT:\n{self._truncate_for_prompt(git_diff)}\n\n"
            f"KIRO IMPLEMENTATION OUTPUT:\n{self._truncate_for_prompt(kiro_output)}\n"
        )

    def _parse_pull_request_description(self, output: str) -> PullRequestDescription:
        cleaned = output.strip()
        title_match = re.search(r"^TITLE:\s*(.+)$", cleaned, flags=re.MULTILINE)
        body_match = re.search(r"^BODY:\s*(.+)$", cleaned, flags=re.MULTILINE | re.DOTALL)

        if title_match is None or body_match is None:
            raise WorkflowError("Kiro did not return a parseable PR description.")

        title = self._short_text(title_match.group(1).strip(), 120)
        body = body_match.group(1).strip()
        if not title or not body:
            raise WorkflowError("Kiro returned an empty PR title or body.")

        return PullRequestDescription(title=title, body=body)

    def _truncate_for_prompt(self, text: str, max_length: int = 6000) -> str:
        cleaned = self._clean_output(text)
        if len(cleaned) <= max_length:
            return cleaned

        return f"{cleaned[:max_length]}\n...[truncated]"

    def _summarize_output(self, output: str) -> str:
        cleaned = self._clean_output(output)
        if len(cleaned) <= 1200:
            return cleaned

        return f"{cleaned[:1200]}\n...[truncated]"

    def _extract_usage_report(self, output: str) -> str | None:
        cleaned = self._clean_output(output)
        usage_patterns = (
            ("Credits used", r"\bcredits?\s+used\s*[:=]\s*([0-9][0-9,]*(?:\.[0-9]+)?)\b"),
            ("Credits used", r"\bused\s+([0-9][0-9,]*(?:\.[0-9]+)?)\s+credits?\b"),
            ("Credits used", r"\b([0-9][0-9,]*(?:\.[0-9]+)?)\s+credits?\s+used\b"),
            ("Tokens used", r"\btokens?\s+used\s*[:=]\s*([0-9][0-9,]*(?:\.[0-9]+)?)\b"),
            ("Tokens used", r"\bused\s+([0-9][0-9,]*(?:\.[0-9]+)?)\s+tokens?\b"),
            ("Tokens used", r"\b([0-9][0-9,]*(?:\.[0-9]+)?)\s+tokens?\s+used\b"),
        )
        for label, pattern in usage_patterns:
            match = re.search(pattern, cleaned, flags=re.IGNORECASE)
            if match:
                return f"{label}: {match.group(1)}"

        return None

    def _kiro_prompt(self, prompt: str, response_path: str | None) -> str:
        if response_path is None:
            return prompt

        return (
            f"{prompt}\n\n"
            "When you are finished, write a concise user-facing response as Markdown to this "
            f"exact absolute path: {response_path}\n\n"
            "The response file must contain only the meaningful result for the Telegram user. "
            "Do not include tool logs, terminal output, ANSI codes, file-read traces, or internal "
            "reasoning. Keep it under 1,200 characters. Mention whether files were changed, "
            "what the user should review, and any important caveats."
        )

    def _clean_output(self, output: str) -> str:
        without_ansi = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
        return without_ansi.strip()

    def _short_text(self, text: str, max_length: int) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= max_length:
            return normalized

        return normalized[: max_length - 3].rstrip() + "..."

    def _redact(self, text: str) -> str:
        return (
            text.replace(self._settings.github_token, "***")
            .replace(self._github_basic_credential(), "***")
            .replace(self._settings.kiro_api_key, "***")
        )

    def _github_auth_header(self) -> str:
        return f"AUTHORIZATION: Basic {self._github_basic_credential()}"

    def _github_basic_credential(self) -> str:
        credential = f"x-access-token:{self._settings.github_token}".encode()
        return base64.b64encode(credential).decode()

    def _base_ref(self) -> str:
        return self._settings.github_base_branch


class _temporary_directory:
    def __init__(self) -> None:
        self._manager = tempfile.TemporaryDirectory(prefix="simple-kirolets-")

    async def __aenter__(self) -> str:
        return await asyncio.to_thread(self._manager.__enter__)

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await asyncio.to_thread(self._manager.__exit__, exc_type, exc, traceback)
