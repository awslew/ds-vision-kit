#!/usr/bin/env python3
"""Generalized OpenAI-compatible vision client with multi-provider support.

Talks to any number of OpenAI-compatible /chat/completions endpoints that accept
``image_url`` content blocks (OpenRouter, OpenAI, a self-hosted vLLM/Ollama,
OpenCode Go's zen proxy, …). At runtime the configured providers are
auto-detected, and requests fail over to the next provider when the current one
errors (rate-limited, quota exhausted, down). Optionally all providers can be
raced and the first valid answer wins.

Configuration (see .env.example):
    Primary provider (the simple, always-works path):
        VISION_API_KEY         required — Bearer token
        VISION_BASE_URL        required — e.g. https://openrouter.ai/api/v1
        VISION_MODEL           required — e.g. openai/gpt-4o-mini, qwen3-vl-32b, mimo-v2.5
    Extra providers (auto-detected, failover fallbacks):
        VISION_EXTRA_PROVIDERS        comma-separated names, e.g. "openrouter,local"
        VISION_PROVIDER_<NAME>_API_KEY / _BASE_URL / _MODEL   per extra provider
        VISION_PROVIDER_ORDER         optional priority, e.g. "local,primary,openrouter"
                                      (default: primary first, then extras in declared order)
        VISION_RACE=1                 race all configured providers, first valid answer wins
        VISION_RACE_TIMEOUT           seconds to wait in race mode (default 45)
    Shared / per-request:
        LANG                   zh | en — ask the model to answer in that language (default zh)
        VISION_ENV_FILE        optional — explicit path to the env file
        VISION_TIMEOUT         optional — per-request timeout in seconds (default 180)
        VISION_TEMPERATURE     optional — sampling temperature; set ~0 for deterministic reads
        VISION_USER_AGENT      optional — override the default browser User-Agent header
        VISION_ORIGIN          optional — add Origin/Referer (some Cloudflare-gated providers
                             need it or they 1010-block non-browser clients)
        VISION_MAX_TOKENS      optional — cap on generated tokens
        VISION_RETRIES         optional — retries on 429/5xx/network per provider (default 2)

Notes
- A browser User-Agent is sent by default. It is harmless for normal providers and
  is the workaround for providers (e.g. opencode.ai/zen) whose edge (Cloudflare)
  returns HTTP 1010 for clients that do not look like a browser.
- When VISION_ORIGIN is set (or a provider's base_url contains "opencode.ai"),
  Origin and Referer headers are added for that provider.
- API keys are redacted from error messages before they reach the user.
"""

from __future__ import annotations

import base64
import http.client
import io
import json
import mimetypes
import os
from pathlib import Path
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

DEFAULT_PROMPT = "Please describe the contents of this image in detail."

LANG_INSTRUCTIONS = {
    "zh": "请使用简体中文回答。",
    "en": "Please respond in English.",
}

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class VisionError(RuntimeError):
    """A safe, user-facing vision request failure."""


@dataclass(frozen=True)
class Provider:
    """One OpenAI-compatible vision endpoint."""
    name: str
    api_key: str
    base_url: str
    model: str


def load_env_file(path: str | os.PathLike[str] | None) -> None:
    if not path:
        return
    env_path = Path(path).expanduser()
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # The env file is the user's explicit configuration: whatever it sets wins,
        # even when the same variable already exists in the system environment.
        if key:
            os.environ[key] = value


def load_default_env() -> None:
    explicit = os.environ.get("VISION_ENV_FILE")
    candidates = [Path(explicit).expanduser()] if explicit else []
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / "agent-vision-toolkit" / "env")
    candidates.extend([
        Path.home() / ".config" / "agent-vision-toolkit" / "env",
        Path(__file__).resolve().parents[1] / ".env",
        Path.cwd() / ".env",
    ])
    for path in candidates:
        load_env_file(path)


def _cfg(name: str) -> str:
    return os.environ.get(name, "").strip()


def _int_env(name: str, default: int) -> int:
    raw = _cfg(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def detect_providers() -> list[Provider]:
    """Return all fully-configured providers in request priority order.

    - The primary provider comes from VISION_API_KEY/BASE_URL/MODEL (the simple,
      always-works path, and the one the scenes were built against).
    - Extra providers come from VISION_EXTRA_PROVIDERS + VISION_PROVIDER_<NAME>_*.
    - VISION_PROVIDER_ORDER reorders them; otherwise primary first, then extras
      in declared order.
    A provider with any of its three variables missing is skipped (with a note).
    """
    providers: list[Provider] = []

    if _cfg("VISION_API_KEY") and _cfg("VISION_BASE_URL") and _cfg("VISION_MODEL"):
        providers.append(Provider("primary", _cfg("VISION_API_KEY"),
                                  _cfg("VISION_BASE_URL"), _cfg("VISION_MODEL")))

    for name in (p.strip() for p in _cfg("VISION_EXTRA_PROVIDERS").split(",")):
        if not name:
            continue
        key = _cfg(f"VISION_PROVIDER_{name.upper()}_API_KEY")
        base = _cfg(f"VISION_PROVIDER_{name.upper()}_BASE_URL")
        model = _cfg(f"VISION_PROVIDER_{name.upper()}_MODEL")
        if key and base and model:
            providers.append(Provider(name.lower(), key, base, model))
        else:
            print(f"vision: provider {name!r} is incomplete (need _API_KEY/_BASE_URL/_MODEL); "
                  f"skipping it", file=sys.stderr)

    order = [p.strip().lower() for p in _cfg("VISION_PROVIDER_ORDER").split(",") if p.strip()]
    if order:
        order_set = set(order)
        by_name = {p.name: p for p in providers}
        providers = ([by_name[n] for n in order if n in by_name]
                     + [p for p in providers if p.name not in order_set])
    return providers


def validate_vision_config() -> None:
    if not detect_providers():
        raise VisionError(
            "No vision provider configured. Set VISION_API_KEY / VISION_BASE_URL / "
            "VISION_MODEL (and add extras via VISION_EXTRA_PROVIDERS if you want "
            "failover). Fill them in the .env file.")


def pil_image_to_data_url(image, min_side: int | None = None) -> str:
    """Encode a PIL Image to a data URL, auto-upscaling small images so the
    vision model can read small text/icons. Upscale is uniform, so relative
    coordinates (ground/detect's 0-1000 grid) still map back to the original
    pixels unchanged."""
    from PIL import Image  # required by callers (region crops), import locally
    if min_side is None:
        min_side = _int_env("VISION_MIN_UPSCALE", 800)
    if min_side > 0:
        w, h = image.size
        if max(w, h) < min_side:
            factor = min_side / max(w, h)
            image = image.resize((round(w * factor), round(h * factor)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def image_path_to_data_url(path: str | os.PathLike[str]) -> str:
    image_path = Path(path).expanduser()
    if not image_path.is_file():
        raise VisionError(f"Image not found: {image_path}")
    mime, _ = mimetypes.guess_type(image_path.name)
    if mime not in {"image/png", "image/jpeg", "image/gif", "image/webp"}:
        raise VisionError("Only PNG, JPEG, GIF, and WebP images are supported")
    min_side = _int_env("VISION_MIN_UPSCALE", 800)
    if min_side <= 0:
        return f"data:{mime};base64,{base64.b64encode(image_path.read_bytes()).decode()}"
    try:
        from PIL import Image
    except ImportError:
        return f"data:{mime};base64,{base64.b64encode(image_path.read_bytes()).decode()}"
    with Image.open(image_path) as image:
        w, h = image.size
        if max(w, h) >= min_side:
            return f"data:{mime};base64,{base64.b64encode(image_path.read_bytes()).decode()}"
        return pil_image_to_data_url(image, min_side)


def _message_text(message: object) -> str:
    if isinstance(message, str):
        return message.strip()
    if isinstance(message, list):
        return "\n".join(
            part["text"] for part in message
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ).strip()
    return ""


def _lang_prefix(apply_lang: bool) -> str:
    if not apply_lang:
        return ""
    instruction = LANG_INSTRUCTIONS.get(_cfg("LANG").lower())
    return f"{instruction}\n\n" if instruction else ""


def _call_provider(provider: Provider, urls: list[str], text: str,
                   max_tokens: int | None, apply_lang: bool, timeout: int) -> str:
    """Send the request to one provider with per-request retries; return text."""
    prefix = _lang_prefix(apply_lang)
    payload: dict = {
        "model": provider.model,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prefix + text}] + [
            {"type": "image_url", "image_url": {"url": url}} for url in urls
        ]}],
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    temperature = _cfg("VISION_TEMPERATURE")
    if temperature:
        try:
            payload["temperature"] = float(temperature)
        except ValueError:
            raise VisionError("VISION_TEMPERATURE must be a number, got "
                              f"{temperature!r}")

    user_agent = _cfg("VISION_USER_AGENT") or DEFAULT_USER_AGENT
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + provider.api_key,
        "Accept": "application/json",
    }
    if user_agent:
        headers["User-Agent"] = user_agent
    origin = _cfg("VISION_ORIGIN") or (
        "https://opencode.ai" if "opencode.ai" in provider.base_url else "")
    if origin:
        headers["Origin"] = origin
        headers["Referer"] = origin + "/"
    request = urllib.request.Request(
        provider.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers=headers,
    )
    retries = _int_env("VISION_RETRIES", 2)
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.load(response)
            try:
                result = _message_text(data["choices"][0]["message"]["content"])
            except (KeyError, IndexError, TypeError) as exc:
                raise VisionError("Vision API returned an incompatible response structure") from exc
            if not result:
                raise VisionError("Vision API returned an empty description")
            return result
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")[:400].replace(provider.api_key, "<redacted>")
            body = body.replace("\r", " ").replace("\n", " ")
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries:
                print(f"vision: HTTP {exc.code}, retrying ({attempt + 1}/{retries})",
                      file=sys.stderr)
                time.sleep(min(2 ** attempt, 4))
                continue
            raise VisionError(f"Vision API HTTP {exc.code}: {body}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError,
                http.client.IncompleteRead) as exc:
            if attempt < retries:
                print(f"vision: {type(exc).__name__}, retrying ({attempt + 1}/{retries})",
                      file=sys.stderr)
                time.sleep(min(2 ** attempt, 4))
                continue
            reason = getattr(exc, "reason", str(exc))
            raise VisionError(f"Vision API network error: {reason}") from exc
        except json.JSONDecodeError as exc:
            raise VisionError("Vision API returned invalid JSON") from exc
    raise VisionError("Vision API request failed")  # pragma: no cover


def _race_providers(providers: list[Provider], urls: list[str], text: str,
                    max_tokens: int | None, apply_lang: bool, timeout: int) -> str:
    """Fire all providers concurrently; return the first valid answer."""
    results: dict[str, tuple[str, str]] = {}  # name -> ("ok", text) | ("err", msg)
    lock = threading.Lock()

    def work(p: Provider) -> None:
        try:
            answer = _call_provider(p, urls, text, max_tokens, apply_lang, timeout)
        except VisionError as exc:
            with lock:
                results[p.name] = ("err", str(exc))
        else:
            with lock:
                results[p.name] = ("ok", answer)

    with ThreadPoolExecutor(max_workers=len(providers)) as executor:
        futures = [executor.submit(work, p) for p in providers]
        deadline = time.time() + _int_env("VISION_RACE_TIMEOUT", 45)
        while time.time() < deadline:
            ok = [v for st, v in results.values() if st == "ok"]
            if ok:
                return ok[0]
            if len(results) >= len(providers):
                break
            time.sleep(0.2)
        for fut in futures:
            fut.cancel()

    errs = [msg for st, msg in results.values() if st == "err"]
    if errs:
        raise VisionError("All vision providers failed (race): " + " | ".join(errs[:3]))
    raise VisionError("Vision race timed out")


def describe_image(image_url: str | list[str], prompt: str | None = None, max_tokens: int = 4096,
                   apply_lang: bool = True) -> str:
    """Describe one data/http image URL (str) or several (list) in a single call.

    Provider selection is automatic: every fully-configured provider is
    detected, and on failure the request fails over to the next one. With
    VISION_RACE=1 all providers are raced and the first valid answer wins.
    """
    validate_vision_config()
    urls = [image_url] if isinstance(image_url, str) else list(image_url)
    if not urls:
        raise VisionError("No image was provided")
    for url in urls:
        if not url.startswith(("data:", "http://", "https://")):
            raise VisionError("Only data URLs or http(s) image URLs are supported")

    text = prompt or DEFAULT_PROMPT
    providers = detect_providers()
    timeout = _int_env("VISION_TIMEOUT", 180)

    if _cfg("VISION_RACE") == "1" and len(providers) > 1:
        return _race_providers(providers, urls, text, max_tokens, apply_lang, timeout)

    first_error: VisionError | None = None
    for index, provider in enumerate(providers):
        try:
            return _call_provider(provider, urls, text, max_tokens, apply_lang, timeout)
        except VisionError as exc:
            if first_error is None:
                first_error = exc
            if index + 1 < len(providers):
                print(f"vision: provider {provider.name} failed ({exc}); "
                      f"failing over to next", file=sys.stderr)
    raise first_error or VisionError("No vision provider configured")
