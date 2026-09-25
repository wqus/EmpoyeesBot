import re


def normalize_lesson_text(text: str | None) -> str:
    """Normalize seeded/admin lesson text for Telegram display without altering meaning."""
    value = (text or "").replace("\\.", ".").strip()
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value


def clean_lesson_title(title: str, position: int | None = None) -> str:
    value = (title or "").strip()
    value = re.sub(r"^Урок\s+\d+\.\s*", "", value, flags=re.IGNORECASE)
    return value or (f"Урок {position}" if position else "Урок")


def numbered_options(options) -> str:
    return "\n".join(f"{i}. {getattr(o, 'text', o.get('text', '') if isinstance(o, dict) else str(o))}" for i, o in enumerate(options, 1))


def split_number_buttons(items, per_row: int = 5):
    rows = []
    row = []
    for i, item in enumerate(items, 1):
        row.append((str(i), item))
        if len(row) >= per_row:
            rows.append(row); row = []
    if row:
        rows.append(row)
    return rows
