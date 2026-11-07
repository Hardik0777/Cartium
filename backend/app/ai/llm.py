"""Hugging Face Inference Providers chat client (OpenAI-compatible API).
Docs: https://huggingface.co/docs/inference-providers"""
import re

import httpx

from app.core.config import settings


class LLMUnavailable(Exception):
    pass


def _plain(text: str) -> str:
    """The chat bubble shows plain text, so turn markdown bullets and bold into readable text."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?m)^\s*[*-]\s+", "• ", text)
    text = re.sub(r"(?m)^\s*[*•-]\s*$\n?", "", text)  # empty bullets left by a cut-off answer
    return text.strip()


def chat(messages: list[dict], max_tokens: int = 1024) -> str:
    if not settings.huggingface_api_key:
        raise LLMUnavailable("No HUGGINGFACE_API_KEY set")
    try:
        res = httpx.post(
            settings.huggingface_chat_url,
            headers={"Authorization": f"Bearer {settings.huggingface_api_key}"},
            json=_body(messages, max_tokens),
            timeout=settings.huggingface_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"Couldn't reach Hugging Face ({type(exc).__name__})") from exc
    if res.status_code != 200:
        raise LLMUnavailable(f"Hugging Face returned HTTP {res.status_code}: {res.text[:200]}")
    try:
        choice = res.json()["choices"][0]
        text = choice["message"]["content"] or ""
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMUnavailable("Unexpected response from Hugging Face") from exc
    if choice.get("finish_reason") == "length":
        # Cut off mid-answer: keep only the complete sentences or lines.
        cut = max(text.rfind(". "), text.rfind(".\n"), text.rfind("\n"))
        text = text[: cut + 1] if cut > 0 else text
    if not text.strip():
        raise LLMUnavailable("The model returned an empty answer")
    return _plain(text)


def _body(messages: list[dict], max_tokens: int) -> dict:
    body = {"model": settings.ai_model_name, "messages": messages, "max_tokens": max_tokens, "temperature": 0.3}
    if "generativelanguage.googleapis.com" in settings.huggingface_chat_url:
        # Gemini "thinking" models spend output tokens on reasoning first; keep that small so answers aren't cut off.
        body["reasoning_effort"] = "low"
    return body
