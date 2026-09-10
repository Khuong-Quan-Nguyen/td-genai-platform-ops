"""PII detection and redaction.

Runs before any user text reaches the model, so raw identifiers never leave
the process. Detectors are deliberately conservative: a false positive costs a
redacted token, a false negative leaks customer data.
"""
import re
from typing import Iterable

from models import PIIMatch

# Canadian SIN: 9 digits, optionally split by space or hyphen.
_SIN_RE = re.compile(r"\b(\d{3})[- ]?(\d{3})[- ]?(\d{3})\b")
# 13-19 digit card numbers, optionally grouped.
_CARD_RE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# North American phone numbers.
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[ .-]?)?\(?([2-9]\d{2})\)?[ .-]?([2-9]\d{2})[ .-]?(\d{4})(?!\d)"
)
# TD-style account/transit numbers: 5-digit transit + 7-12 digit account.
_ACCOUNT_RE = re.compile(r"\b\d{5}[- ]\d{3}[- ]\d{7,12}\b")


def _luhn_ok(digits: str) -> bool:
    """Luhn checksum - keeps random long numbers from being flagged as cards."""
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _mask(text: str, keep_last: int = 0) -> str:
    if keep_last and len(text) > keep_last:
        return "*" * (len(text) - keep_last) + text[-keep_last:]
    return "*" * len(text)


def _mask_email(text: str) -> str:
    local, _, domain = text.partition("@")
    head = local[0] if local else ""
    return f"{head}{'*' * max(len(local) - 1, 1)}@{domain}"


def detect(text: str) -> list[PIIMatch]:
    """Return every PII span found in `text`, ordered by position.

    Overlapping hits are resolved by preferring the earlier, then longer match,
    so a card number inside an account string is reported once.
    """
    found: list[PIIMatch] = []

    for match in _ACCOUNT_RE.finditer(text):
        found.append(
            PIIMatch(kind="bank_account", redacted=_mask(match.group(), keep_last=4),
                     start=match.start(), end=match.end())
        )

    for match in _CARD_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            found.append(
                PIIMatch(kind="credit_card", redacted=_mask(match.group(), keep_last=4),
                         start=match.start(), end=match.end())
            )

    for match in _SIN_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if _luhn_ok(digits):  # SINs are Luhn-valid too
            found.append(
                PIIMatch(kind="sin", redacted=_mask(match.group()),
                         start=match.start(), end=match.end())
            )

    for match in _EMAIL_RE.finditer(text):
        found.append(
            PIIMatch(kind="email", redacted=_mask_email(match.group()),
                     start=match.start(), end=match.end())
        )

    for match in _PHONE_RE.finditer(text):
        found.append(
            PIIMatch(kind="phone", redacted=_mask(match.group(), keep_last=4),
                     start=match.start(), end=match.end())
        )

    return _dedupe(found)


def _dedupe(matches: Iterable[PIIMatch]) -> list[PIIMatch]:
    ordered = sorted(matches, key=lambda m: (m.start, -(m.end - m.start)))
    kept: list[PIIMatch] = []
    for candidate in ordered:
        if any(candidate.start < k.end and k.start < candidate.end for k in kept):
            continue
        kept.append(candidate)
    return kept


def redact(text: str, matches: list[PIIMatch] | None = None) -> str:
    """Replace each detected span with a typed placeholder."""
    matches = detect(text) if matches is None else matches
    if not matches:
        return text
    out, cursor = [], 0
    for match in sorted(matches, key=lambda m: m.start):
        out.append(text[cursor:match.start])
        out.append(f"[REDACTED_{match.kind.upper()}]")
        cursor = match.end
    out.append(text[cursor:])
    return "".join(out)


def scan(text: str) -> tuple[str, list[PIIMatch]]:
    """Convenience: return (redacted_text, matches)."""
    matches = detect(text)
    return redact(text, matches), matches
