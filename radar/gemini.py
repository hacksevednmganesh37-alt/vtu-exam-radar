"""Small wrapper around the Gemini API (google-genai package)."""
import json
import logging
import os
import re
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

# Change this in your Codespace if Google releases a newer model:
#   export GEMINI_MODEL="gemini-3.5-flash"
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
# Each model has its own free-tier quota. If one is used up or busy we try the next.
FALLBACKS = [m.strip() for m in os.environ.get(
    "GEMINI_FALLBACK_MODELS",
    "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-flash-lite-latest,gemini-2.5-flash").split(",") if m.strip()]
_exhausted: dict[str, float] = {}   # model -> time it ran out (skip it for a while)

_client = None


def client() -> genai.Client:
    global _client
    if _client is None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it as a Codespaces secret "
                "(get a key at aistudio.google.com/apikey)."
            )
        _client = genai.Client(api_key=key, http_options=types.HttpOptions(api_version="v1beta"))
    return _client


def generate(contents, config):
    """generate_content with model fallback when a model's quota is used up."""
    models = [m for m in dict.fromkeys([MODEL, *FALLBACKS])
              if time.time() - _exhausted.get(m, 0) > 15 * 60] or [MODEL]
    last_err = None
    for model in models:
        try:
            return client().models.generate_content(model=model, contents=contents, config=config)
        except genai_errors.APIError as err:  # 429 quota, 404 retired model, 5xx overloaded
            if getattr(err, "code", None) not in (429, 404, 500, 503):
                raise
            logging.warning("Gemini model %s unavailable (%s), trying the next one", model, err.code)
            _exhausted[model] = time.time()
            last_err = err
    raise last_err


def upload(path: str):
    """Upload a PDF so Gemini can read it."""
    return client().files.upload(file=path)


def ask_json(prompt: str, files: list | None = None) -> dict | list:
    """Ask Gemini and get JSON back."""
    contents = [*(files or []), prompt]
    resp = generate(contents, types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.2,
    ))
    return json.loads(resp.text)


def ask_web(prompt: str) -> tuple[dict | list | None, list[dict]]:
    """Ask Gemini with live Google Search. Returns (parsed JSON or None, sources)."""
    resp = generate(
        prompt + "\n\nAnswer ONLY with JSON inside a ```json code block.",
        types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.2,
        ),
    )
    text = resp.text or ""
    data = None
    match = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
    try:
        data = json.loads(match.group(1) if match else text)
    except (json.JSONDecodeError, AttributeError):
        data = None

    sources = []
    try:
        for chunk in resp.candidates[0].grounding_metadata.grounding_chunks or []:
            if chunk.web:
                sources.append({"title": chunk.web.title, "url": chunk.web.uri})
    except (AttributeError, IndexError, TypeError):
        pass
    return data, sources
