from __future__ import annotations


def money(value: float | int | None) -> str:
    value = float(value or 0)
    return f"C$ {value:,.2f}"


def compact_money(value: float | int | None) -> str:
    value = float(value or 0)
    if value == 0:
        return "$ 0"
    return f"$ {value:,.0f}"


def clean_phone(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit() or ch == "+")


def truncate_field(text: str, max_chars: int = 180) -> str:
    text = " ".join((text or "").split())
    return text[: max_chars - 1] + "…" if len(text) > max_chars else text
