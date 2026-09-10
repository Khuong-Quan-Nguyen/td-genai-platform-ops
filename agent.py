"""Claude agentic layer.

Owns the model call and nothing else: callers hand it text that has already
been PII-redacted by `security.py`, and get back text plus token usage.
"""
import os
from dataclasses import dataclass

import anthropic

from models import ContextDomain

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")
MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "8000"))
EFFORT = os.getenv("ANTHROPIC_EFFORT", "high")

_BASE_SYSTEM = (
    "You are the TD GenAI Platform code assistant, serving engineers inside a "
    "Canadian retail bank. Be precise and concise. Prefer working code with a "
    "short explanation over prose. If a request is ambiguous, state the "
    "assumption you are making and answer anyway."
)

_CONTEXT_SYSTEM = {
    ContextDomain.GENERAL: "",
    ContextDomain.FINANCIAL_SERVICES: (
        " This request is in a financial-services context. Account for OSFI and "
        "PIPEDA obligations, data residency, and auditability in your answer. "
        "Note where a control or sign-off would normally be required. Any "
        "customer identifiers have already been redacted and appear as "
        "[REDACTED_*] placeholders - never ask the user to supply them again."
    ),
}


class AgentError(RuntimeError):
    """Raised when the model call fails or is declined."""


@dataclass
class AgentResult:
    text: str
    input_tokens: int
    output_tokens: int
    model: str

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def _client() -> anthropic.Anthropic:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise AgentError(
            "ANTHROPIC_API_KEY is not set. Add it to .env and restart the service."
        )
    return anthropic.Anthropic()


def run(query: str, context: ContextDomain = ContextDomain.GENERAL) -> AgentResult:
    """Send one redacted query to Claude and return the completion.

    Streams the response so large answers don't hit the SDK's HTTP timeout, and
    enables server-side fallbacks so a safety refusal is rerouted instead of
    surfacing to the user as a dead end.
    """
    client = _client()
    system = _BASE_SYSTEM + _CONTEXT_SYSTEM[context]

    try:
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            thinking={"type": "adaptive"},
            output_config={"effort": EFFORT},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": query}],
        ) as stream:
            message = stream.get_final_message()
    except anthropic.APIStatusError as exc:
        raise AgentError(f"Claude API error ({exc.status_code}): {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise AgentError(f"Could not reach the Claude API: {exc}") from exc

    if message.stop_reason == "refusal":
        category = getattr(message.stop_details, "category", None)
        raise AgentError(f"Request declined by safety classifier (category: {category}).")

    text = "".join(
        block.text for block in message.content if block.type == "text"
    ).strip()
    if not text:
        raise AgentError("Model returned no text content.")

    return AgentResult(
        text=text,
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
        model=message.model,
    )
