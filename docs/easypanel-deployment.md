# EasyPanel Deployment Guide

This guide deploys Simple Kirolets as one EasyPanel App Service.

Simple Kirolets uses Telegram polling, so it does not need a public domain, webhook route,
Redis service, or worker service. The deployed container makes outbound HTTPS requests to
Telegram, Kiro, and GitHub.

## Deployment Shape

```text
EasyPanel App Service
  -> Dockerfile
  -> simple-kirolets command
  -> Telegram polling
  -> Kiro CLI
  -> GitHub PR or YOLO push
```

## Prerequisites

You need:

- An EasyPanel project.
- This repository connected to GitHub.
- A Telegram bot token from BotFather.
- A Kiro API key.
- A GitHub token for the repository Kiro will edit.
- The HTTPS URL of the target GitHub repository.

## GitHub Token Permissions

For a fine-grained GitHub token, start with:

- Metadata: read
- Contents: read/write
- Pull requests: read/write

If `YOLO=true`, the token must also be allowed to push directly to `GITHUB_BASE_BRANCH`.
Branch protection rules may still reject direct pushes.

For a classic personal access token, the course-friendly shortcut is the `repo` scope.

## EasyPanel App Service

Create one App Service.

Recommended settings:

```text
Service name: simple-kirolets
Source: GitHub
Build method: Dockerfile
Dockerfile path: Dockerfile
Command: simple-kirolets
Public domain: not required
```

If EasyPanel leaves the command blank, the Dockerfile default already runs:

```bash
simple-kirolets
```

## Environment Variables

Add these variables to the EasyPanel App Service.

### Telegram

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_IDS=
```

`TELEGRAM_BOT_TOKEN` comes from BotFather.

`TELEGRAM_ALLOWED_USER_IDS` is optional. Leave it empty to allow anyone who can message the
bot. Set it to comma-separated numeric Telegram user IDs to restrict access:

```env
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321
```

To find your Telegram user ID, use a bot such as `@userinfobot`, or temporarily log
incoming `effective_user.id` during development.

### GitHub

```env
GITHUB_REPOSITORY_URL=
GITHUB_TOKEN=
GITHUB_BASE_BRANCH=main
GIT_CACHE_DIR=/app/.simple-kirolets/git-cache
```

Example:

```env
GITHUB_REPOSITORY_URL=https://github.com/your-org/your-repo.git
```

`GITHUB_REPOSITORY_URL` is the repository Kiro will modify. It can be the same repo as
Simple Kirolets, but it is usually the learner's target project.

### Kiro

```env
KIRO_API_KEY=
KIRO_TRUST_TOOLS=read,grep,write,bash
KIRO_TIMEOUT_SECONDS=1800
```

`KIRO_API_KEY` authenticates Kiro CLI in headless mode.

`KIRO_TRUST_TOOLS` controls which tools Kiro may use without interactive approval. Keep this
as narrow as the lesson allows.

### Runtime

```env
PROGRESS_UPDATE_INTERVAL_SECONDS=30
YOLO=false
LOG_LEVEL=INFO
```

`PROGRESS_UPDATE_INTERVAL_SECONDS` controls Telegram heartbeat messages while Kiro is
working.

`YOLO=false` opens pull requests.

`YOLO=true` pushes directly to `GITHUB_BASE_BRANCH`.

## Full Environment Template

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_IDS=
LOG_LEVEL=INFO

GITHUB_REPOSITORY_URL=
GITHUB_TOKEN=
GITHUB_BASE_BRANCH=main
GIT_CACHE_DIR=/app/.simple-kirolets/git-cache

KIRO_API_KEY=
KIRO_TRUST_TOOLS=read,grep,write,bash
KIRO_TIMEOUT_SECONDS=1800

PROGRESS_UPDATE_INTERVAL_SECONDS=30
YOLO=false
```

## Persistent Volume

Simple Kirolets uses a bare Git cache so it does not need to clone the full target repo on
every request.

Add a persistent volume to the EasyPanel service:

```text
Mount path: /app/.simple-kirolets
```

Then keep:

```env
GIT_CACHE_DIR=/app/.simple-kirolets/git-cache
```

The app still works without this volume, but the cache is rebuilt whenever the container is
recreated.

## First Deploy

1. Create the EasyPanel App Service.
2. Connect this GitHub repository.
3. Use the repository Dockerfile.
4. Add the environment variables.
5. Add the persistent volume if desired.
6. Deploy.
7. Open the service logs.
8. Confirm the bot starts without errors.

## Smoke Test

In Telegram:

1. Send `/start`.
2. Send a small request:

```text
Add a short sentence to the README saying this repo is managed through Simple Kirolets.
```

Expected result:

1. The bot acknowledges the request.
2. The bot sends heartbeat messages while Kiro works.
3. The bot reports Kiro's response.
4. With `YOLO=false`, the bot sends a GitHub PR link.
5. With `YOLO=true`, the bot confirms it pushed directly to the base branch.

## Troubleshooting

### The bot does not respond in Telegram

Check:

- `TELEGRAM_BOT_TOKEN` is correct.
- The EasyPanel service is running.
- The service logs do not show startup errors.
- Only one running service is polling the same Telegram bot token.

### The bot says you are not allowed

Check:

- `TELEGRAM_ALLOWED_USER_IDS` contains your numeric Telegram user ID.
- There are no spaces or invalid values other than comma separators.
- Leave `TELEGRAM_ALLOWED_USER_IDS` empty while testing if you are unsure.

### Kiro fails

Check:

- `KIRO_API_KEY` is set.
- The Docker build installed `kiro-cli` successfully.
- `KIRO_TRUST_TOOLS` includes the tools needed for the task.

### GitHub PR creation fails

Check:

- `GITHUB_TOKEN` has Contents read/write.
- `GITHUB_TOKEN` has Pull requests read/write.
- `GITHUB_REPOSITORY_URL` is an HTTPS GitHub repo URL.
- `GITHUB_BASE_BRANCH` exists.

### YOLO push fails

Check:

- `YOLO=true` is intentional.
- The token can push to `GITHUB_BASE_BRANCH`.
- Branch protection allows direct pushes by that token.

## Course Notes

This deployment is intentionally small. It lets learners see the whole productivity loop
without Redis, workers, webhooks, or cloud storage:

```text
Telegram -> Kiro -> GitHub -> Telegram
```

Once students understand this version, you can introduce the production Kirolets
architecture with Redis, split bot/worker services, voice transcription, and webhooks.
