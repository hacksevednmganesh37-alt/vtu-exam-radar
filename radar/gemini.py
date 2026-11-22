"""Small wrapper around the Gemini API (google-genai package)."""
import json
import os
import re

from google import genai
from google.genai import types

# Change this in your Codespace if Google releases a newer model:
#   export GEMINI_MODEL="gemini-2.5-flash"
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

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


def upload(path: str):
    """Upload a PDF so Gemini can read it."""
    return client().files.upload(file=path)


def ask_json(prompt: str, files: list | None = None) -> dict | list:
    """Ask Gemini and get JSON back."""
    contents = [*(files or []), prompt]
    resp = client().models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    return json.loads(resp.text)


def ask_web(prompt: str) -> tuple[dict | list | None, list[dict]]:
    """Ask Gemini with live Google Search. Returns (parsed JSON or None, sources)."""
    resp = client().models.generate_content(
        model=MODEL,
        contents=prompt
        + "\n\nAnswer ONLY with JSON inside a ```json code block.",
        config=types.GenerateContentConfig(
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
