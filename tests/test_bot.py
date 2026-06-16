from simple_kirolets.bot import _kiro_response_message


def test_kiro_response_message_uses_fallback_for_empty_summary():
    assert (
        _kiro_response_message("  ")
        == "<b>Kiro response</b>\n\n"
        "Kiro finished without returning a response.\n\n"
        "<i>Usage: not reported by Kiro CLI</i>"
    )


def test_kiro_response_message_truncates_long_summary():
    message = _kiro_response_message("a" * 4000)

    assert message.startswith("<b>Kiro response</b>\n\naaa")
    assert "...[truncated]" in message
    assert message.endswith("<i>Usage: not reported by Kiro CLI</i>")
    assert len(message) < 3700


def test_kiro_response_message_formats_markdown_for_telegram_html():
    message = _kiro_response_message(
        "# Customer Summary\n\n"
        "## Northstar Bakes\n"
        "- **Stage:** Discovery\n"
        "- Read `customers/overview.md`\n"
        "---\n"
        "No files were changed.",
        usage_report="Credits used: 12.5",
    )

    assert "<b>Customer Summary</b>" in message
    assert "<b>Northstar Bakes</b>" in message
    assert "• <b>Stage:</b> Discovery" in message
    assert "• Read <code>customers/overview.md</code>" in message
    assert "---" not in message
    assert "<i>Credits used: 12.5</i>" in message
