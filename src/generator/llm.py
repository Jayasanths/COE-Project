"""
Local LLM client (tier 1 only).

Talks to Ollama on localhost:11434. Deliberately built on `urllib` from the
standard library rather than httpx: the generator must be importable and
runnable in a test environment with nothing installed, and the eval harness
must not need a running model to produce numbers.

The client is off by default. Tier 1 is attempted only when
`PSYCH_HANDOVER_OLLAMA=1` is set. That matches the thermal guidance for a
fanless M4 Air and, more importantly, makes tier 2 the default path so the
demo can never be dependent on a model being warm.

Nothing in this module is a policy control. The consent filter has already run
by the time anything here is called — the model only ever sees permitted text.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT_S = float(os.environ.get("OLLAMA_TIMEOUT", "20"))
SEED = 42

SYSTEM_PROMPT = (
    "You are a clinical handover assistant. Summarise only the provided "
    "permitted content. Do not invent, infer, or hallucinate clinical details. "
    "If uncertain, say so. Reply with a JSON object with a single key "
    '"summary" whose value is a plain-text paragraph of at most 90 words. '
    "Do not add commentary outside the JSON."
)


class LLMUnavailable(RuntimeError):
    """Raised whenever tier 1 cannot produce a trustworthy result.

    Every failure mode collapses into this one exception — connection refused,
    timeout, malformed JSON, schema violation, ungrounded output. The caller
    does not need to distinguish them, because the response to all of them is
    identical: drop to tier 2.
    """


@dataclass(frozen=True)
class LLMResult:
    summary: str
    model: str


def is_enabled() -> bool:
    """Tier 1 is opt-in. Absent the flag, the ladder starts at tier 2."""
    return os.environ.get("PSYCH_HANDOVER_OLLAMA", "0") == "1"


def _validate_payload(raw: str) -> str:
    """Parse and schema-check the model's reply.

    Uses Pydantic when it is installed (as pinned in pyproject) and an
    equivalent stdlib check when it is not, so validation strictness does not
    silently depend on the environment.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMUnavailable(f"tier 1 returned non-JSON: {exc}") from exc

    try:
        from pydantic import BaseModel, Field, ValidationError

        class _Reply(BaseModel):
            summary: str = Field(min_length=1, max_length=2000)

        try:
            return _Reply(**data).summary.strip()
        except ValidationError as exc:
            raise LLMUnavailable(f"tier 1 failed schema validation: {exc}") from exc
    except ImportError:
        pass

    if not isinstance(data, dict):
        raise LLMUnavailable("tier 1 reply was not a JSON object")
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise LLMUnavailable("tier 1 reply had no usable 'summary' field")
    if len(summary) > 2000:
        raise LLMUnavailable("tier 1 reply exceeded the length bound")
    return summary.strip()


def generate(prompt: str) -> LLMResult:
    """Call Ollama once. Any problem at all raises LLMUnavailable.

    temperature=0 and a fixed seed make the call as close to reproducible as a
    local model gets. It is still not deterministic across model versions,
    which is exactly why tier 1 output is never trusted without the grounding
    check applied by the caller.
    """
    if not is_enabled():
        raise LLMUnavailable("tier 1 disabled (set PSYCH_HANDOVER_OLLAMA=1 to enable)")

    body = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "system": SYSTEM_PROMPT,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "seed": SEED},
        }
    ).encode()

    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_S) as response:
            envelope = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LLMUnavailable(f"tier 1 unreachable: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LLMUnavailable(f"tier 1 envelope was not JSON: {exc}") from exc

    return LLMResult(
        summary=_validate_payload(envelope.get("response", "")), model=OLLAMA_MODEL
    )
