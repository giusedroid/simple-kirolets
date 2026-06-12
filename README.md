# Simple Kirolets

Simple Kirolets is the single-service teaching version of Kirolets.

It lets a Telegram user send a text request, runs Kiro CLI headlessly against a configured
GitHub repository, and then either opens a pull request or pushes directly to the base branch
when `YOLO=true`.

This folder is intentionally standalone. It does not reuse the root Kirolets package and it
does not require Redis, a separate worker service, or Amazon Transcribe.

## Architecture

```text
Telegram text message
  -> simple-kirolets polling bot
  -> temporary Git worktree from bare cache
  -> Kiro CLI implementation pass
  -> Git commit
  -> Kiro CLI PR-description pass
  -> GitHub PR or YOLO direct push
  -> Telegram result message
```

## What This Version Teaches

- Telegram polling.
- Environment-driven configuration.
- Headless Kiro CLI usage.
- Bare Git cache plus temporary worktrees.
- GitHub PR creation with the REST API.
- Optional `YOLO=true` direct-to-base-branch mode.
- Single EasyPanel App Service deployment.

## Requirements

- uv
- Python 3.14
- A Telegram bot token from BotFather
- A GitHub token for the target repo
- A Kiro API key

## Local Setup

```powershell
cd simple
uv python install 3.14
uv sync --dev
Copy-Item .env.example .env
```

Edit `.env` and set the required secrets.

## Run

```powershell
uv run simple-kirolets
```

## Test

```powershell
uv run pytest
uv run ruff check .
```

## Environment Variables

```env
TELEGRAM_BOT_TOKEN=
LOG_LEVEL=INFO

GITHUB_REPOSITORY_URL=
GITHUB_TOKEN=
GITHUB_BASE_BRANCH=main
GIT_CACHE_DIR=.simple-kirolets/git-cache

KIRO_API_KEY=
KIRO_TRUST_TOOLS=read,grep,write,bash
KIRO_TIMEOUT_SECONDS=1800

PROGRESS_UPDATE_INTERVAL_SECONDS=30
YOLO=false
```

## EasyPanel Single-Service Deployment

Create one EasyPanel App Service:

1. Select the GitHub repository as the source.
2. Set the build context or Dockerfile path to the `simple` folder if EasyPanel exposes that option.
3. Build with `simple/Dockerfile`.
4. Use the default command:

```bash
simple-kirolets
```

5. Add the environment variables from `.env.example`.
6. Deploy the service.
7. Message the Telegram bot with a text request.

This version uses Telegram polling, so you do not need to configure a public domain or webhook
for the bot.

## YOLO Mode

Default mode:

```env
YOLO=false
```

Kirolets pushes a request branch and opens a GitHub PR.

YOLO mode:

```env
YOLO=true
```

Kirolets commits Kiro's changes and pushes directly to `GITHUB_BASE_BRANCH`.

Use YOLO mode only in repositories where direct bot commits are acceptable. GitHub branch
protection can still reject direct pushes.

## From Simple To Full Kirolets

This project is deliberately simple for learners. The full root project adds:

- Redis queueing.
- Separate bot and worker services.
- Voice-note transcription with S3 and Amazon Transcribe.
- Better production scaling boundaries.

Start here to understand the loop. Graduate to the root project when the learner is ready
to see how the same idea becomes a more production-shaped system.
