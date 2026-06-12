import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from simple_kirolets.config import Settings, load_settings
from simple_kirolets.github_workflow import GitHubWorkflow, WorkflowError
from simple_kirolets.progress import progress_updates


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    if not await _authorize(update, context):
        return

    await update.message.reply_text("Simple Kirolets is online. Send me a text task for Kiro.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    if not await _authorize(update, context):
        return

    await update.message.reply_text("Send a text message describing the code change you want.")


async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    if not await _authorize(update, context):
        return

    if update.message.voice is not None:
        await update.message.reply_text(
            "This simple teaching version only supports text messages. "
            "The full Kirolets app supports voice transcription."
        )
        return

    request_text = (update.message.text or "").strip()
    if not request_text:
        await update.message.reply_text("Send me a text task for Kiro.")
        return

    settings: Settings = context.application.bot_data["settings"]
    workflow = GitHubWorkflow(settings)

    await update.message.reply_text("Got it. I am running Kiro against the configured repo now.")

    try:
        async with progress_updates(
            update.message.reply_text,
            "Kiro is still working. I will send the result when it is ready.",
            settings.progress_update_interval_seconds,
        ):
            result = await workflow.execute(request_text, _user_label(update))

        await update.message.reply_text(_kiro_response_message(result.kiro_response))

        if result.changed and result.pushed_to_base:
            await update.message.reply_text(
                f"Done. YOLO mode is enabled, so I pushed directly to "
                f"`{settings.github_base_branch}`."
            )
        elif result.changed and result.pr_url:
            await update.message.reply_text(f"Done. I opened a PR for review: {result.pr_url}")
        else:
            await update.message.reply_text("Kiro completed, but there were no file changes to publish.")
    except WorkflowError as exc:
        await update.message.reply_text(f"I could not complete the request: {exc}")


def build_application() -> Application:
    settings = load_settings()
    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        level=settings.log_level,
    )

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data["settings"] = settings
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT | filters.VOICE, process_message))
    return application


def main() -> None:
    application = build_application()
    application.run_polling(allowed_updates=["message"])


def _user_label(update: Update) -> str:
    if update.effective_user is None:
        return "unknown"

    if update.effective_user.username:
        return update.effective_user.username

    return str(update.effective_user.id)


def _kiro_response_message(summary: str) -> str:
    response = summary.strip() or "Kiro finished without returning a response."
    max_length = 3500
    if len(response) > max_length:
        response = f"{response[:max_length].rstrip()}\n...[truncated]"

    return f"Kiro response:\n\n{response}"


async def _authorize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    settings: Settings = context.application.bot_data["settings"]
    allowed_user_ids = settings.telegram_allowed_user_ids
    if not allowed_user_ids:
        return True

    user_id = update.effective_user.id if update.effective_user is not None else None
    if user_id in allowed_user_ids:
        return True

    if update.message is not None:
        await update.message.reply_text("You are not allowed to use this bot.")

    return False
