# utils/text_utils.py

import html

def format_html_pre(text: str) -> str:
    """Оборачивает в <pre> с экранированием HTML."""
    return f"<pre>{html.escape(text)}</pre>"
