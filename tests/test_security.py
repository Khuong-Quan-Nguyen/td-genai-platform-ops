"""PII detector tests.

These are the tests that matter most: a false negative here means customer
data reaches the model. No API key or network access required.
"""
import pytest

import security


@pytest.mark.parametrize(
    "text,kind",
    [
        ("My SIN is 046 454 286", "sin"),
        ("SIN: 046-454-286", "sin"),
        ("card 4532015112830366", "credit_card"),
        ("card 4532 0151 1283 0366", "credit_card"),
        ("Visa 4111-1111-1111-1111 on file", "credit_card"),
        ("reach me at john.smith@td.com", "email"),
        ("call 416-555-0142", "phone"),
        ("call (416) 555-0142", "phone"),
        ("call +1 416 555 0142", "phone"),
        ("account 12345-678-9012345", "bank_account"),
    ],
)
def test_detects(text, kind):
    kinds = {m.kind for m in security.detect(text)}
    assert kind in kinds, f"expected {kind} in {kinds} for {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "How do I write a retry decorator in Python?",
        "Refactor this to use async/await",
        "The build failed with exit code 137",
        "Set timeout to 30000 milliseconds",
        "Order 12345 shipped",
    ],
)
def test_no_false_positives(text):
    assert security.detect(text) == [], f"false positive on {text!r}"


def test_luhn_rejects_random_digits():
    """A 16-digit number that fails Luhn is not a card."""
    assert not any(m.kind == "credit_card" for m in security.detect("id 1234567890123456"))


def test_redaction_removes_raw_value():
    text = "SIN 046 454 286 and card 4532015112830366"
    redacted = security.redact(text)
    assert "046 454 286" not in redacted
    assert "4532015112830366" not in redacted
    assert "[REDACTED_SIN]" in redacted
    assert "[REDACTED_CREDIT_CARD]" in redacted


def test_redaction_preserves_surrounding_text():
    """Regression: the card pattern used to swallow the trailing space."""
    redacted = security.redact("Charge card 4532015112830366 please")
    assert redacted == "Charge card [REDACTED_CREDIT_CARD] please"


def test_clean_text_passes_through_unchanged():
    text = "How do I write a retry decorator in Python?"
    assert security.redact(text) == text


def test_overlapping_matches_reported_once():
    """A card number inside an account string must not double-report."""
    matches = security.detect("account 12345-678-9012345 review")
    spans = [(m.start, m.end) for m in matches]
    for i, a in enumerate(spans):
        for b in spans[i + 1:]:
            assert a[1] <= b[0] or b[1] <= a[0], f"overlap: {spans}"


def test_masked_values_leak_nothing():
    """The `redacted` field is shown in the UI - it must not carry raw PII."""
    for match in security.detect("SIN 046 454 286, card 4532015112830366"):
        assert "046454286" not in match.redacted.replace(" ", "")
        assert "4532015112830366" not in match.redacted.replace(" ", "")


def test_scan_returns_both():
    redacted, matches = security.scan("email me at a.b@td.com")
    assert "[REDACTED_EMAIL]" in redacted
    assert len(matches) == 1
