from __future__ import annotations

_OPERATOR_TEXT_REPLACEMENTS = {
    "\ufeff": "",
    "\u200b": "",
    "\u200c": "",
    "\u200d": "",
    "â†’": "->",
    "→": "->",
    "â€”": "-",
    "—": "-",
    "–": "-",
    "âœ“": "[OK]",
    "✓": "[OK]",
    "âœ…": "[OK]",
    "✅": "[OK]",
    "â": "[OK]",
    "âŒ": "[FAIL]",
    "❌": "[FAIL]",
    "âš ï¸": "[WARN]",
    "⚠️": "[WARN]",
    "⚠": "[WARN]",
    "â•": "=",
    "â•‘": "|",
    "â•”": "+",
    "â•—": "+",
    "â•š": "+",
    "â•": "+",
    "â”€": "-",
    "â”‚": "|",
    "â”Œ": "+",
    "â”": "+",
    "â””": "+",
    "â”˜": "+",
}


def normalize_operator_text(value: object) -> str:
    """Return text that remains readable in Windows terminals, logs, and Telegram."""
    text = str(value)
    for bad, good in _OPERATOR_TEXT_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text
