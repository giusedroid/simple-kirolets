from simple_kirolets.bot import _kiro_response_message


def test_kiro_response_message_uses_fallback_for_empty_summary():
    assert _kiro_response_message("  ") == "Kiro response:\n\nKiro finished without returning a response."


def test_kiro_response_message_truncates_long_summary():
    message = _kiro_response_message("a" * 4000)

    assert message.startswith("Kiro response:\n\naaa")
    assert message.endswith("...[truncated]")
    assert len(message) < 3700
