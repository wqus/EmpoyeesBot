import html

def escape_html(value: str | None) -> str:
    return html.escape(value or '')
