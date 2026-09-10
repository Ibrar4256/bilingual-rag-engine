"""
LLM Provider Abstraction (R22)

All text-generation in this project goes through this module — never call
an LLM API directly. This gives us:
  1. One place to swap providers (Gemini, Groq, OpenRouter)
  2. Every call logs which provider served it (for UAT evidence)
  3. The active provider is read from app_config DB table (set via Admin UI)

Callers should use generate_with_retry() rather than calling provider.generate()
directly — free-tier rate limits (429 Too Many Requests) are a real, observed
failure mode under normal ETL load (see bilingual_etl/load/embeddings.py for
the same pattern applied to embedding calls). A per-minute rate limit window
needs a backoff long enough to actually clear it, not a quick retry.

Usage:
    provider = get_llm_provider()
    response = generate_with_retry(provider, "Translate this to English: ...", system_prompt="...")
"""

import json
import os
import time
from abc import ABC, abstractmethod

import requests
from loguru import logger

GENERATE_MAX_RETRIES = 6
GENERATE_INITIAL_BACKOFF_SECONDS = 30


class LLMProvider(ABC):
    """Base interface — every backend implements this."""

    name: str = "base"

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        ...


class GeminiLLM(LLMProvider):
    """Google Gemini (gemini-2.5-flash) — free tier, no credit card."""

    name = "gemini"

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set in environment")
        self.model = "gemini-2.5-flash"
        self.url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": system_prompt}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will follow these instructions."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {"contents": contents}
        resp = requests.post(self.url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        logger.info(f"LLM call served by provider=gemini model={self.model}")
        return text.strip()


class GroqLLM(LLMProvider):
    """Groq — fast free-tier inference on open-weight models."""

    name = "groq"

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not set in environment")
        self.model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": self.model, "messages": messages, "temperature": 0.3}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        resp = requests.post(self.url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        text = data["choices"][0]["message"]["content"]
        logger.info(f"LLM call served by provider=groq model={self.model}")
        return text.strip()


class OpenRouterLLM(LLMProvider):
    """OpenRouter — access to many models through one API."""

    name = "openrouter"

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set in environment")
        self.model = os.getenv("OPENROUTER_MODEL", "nex-agi/nex-n2.5-pro:free")
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": self.model, "messages": messages}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        resp = requests.post(self.url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        text = data["choices"][0]["message"]["content"]
        logger.info(f"LLM call served by provider=openrouter model={self.model}")
        return text.strip()


class NineRouterLLM(LLMProvider):
    """9Router — local AI router with 3-tier fallback across 60+ providers."""

    name = "9router"

    def __init__(self):
        self.api_key = os.getenv("NINE_ROUTER_API_KEY", "")
        if not self.api_key:
            raise ValueError("NINE_ROUTER_API_KEY not set in environment")
        base_url = os.getenv("NINE_ROUTER_URL", "http://localhost:20128")
        self.url = f"{base_url}/v1/chat/completions"
        self.model = os.getenv("NINE_ROUTER_LLM_MODEL", "oc/mimo-v2.5-free")

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": self.model, "messages": messages, "temperature": 0.3, "stream": False}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        resp = requests.post(self.url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        text = data["choices"][0]["message"]["content"]
        logger.info(f"LLM call served by provider=9router model={self.model}")
        return text.strip()


class CerebrasLLM(LLMProvider):
    """Cerebras — fastest free-tier inference."""

    name = "cerebras"

    def __init__(self):
        self.api_key = os.getenv("CEREBRAS_API_KEY", "")
        if not self.api_key:
            raise ValueError("CEREBRAS_API_KEY not set in environment")
        self.model = os.getenv("CEREBRAS_MODEL", "qwen-3.8-27b")
        self.url = "https://api.cerebras.ai/v1/chat/completions"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": self.model, "messages": messages, "temperature": 0.3}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        resp = requests.post(self.url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        text = data["choices"][0]["message"]["content"]
        logger.info(f"LLM call served by provider=cerebras model={self.model}")
        return text.strip()


class SambaNovaLLM(LLMProvider):
    """SambaNova Cloud — free-tier with fast inference on open models."""

    name = "sambanova"

    def __init__(self):
        self.api_key = os.getenv("SAMBANOVA_API_KEY", "")
        if not self.api_key:
            raise ValueError("SAMBANOVA_API_KEY not set in environment")
        self.model = os.getenv("SAMBANOVA_MODEL", "Meta-Llama-3.3-70B-Instruct")
        self.url = "https://api.sambanova.ai/v1/chat/completions"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": self.model, "messages": messages, "temperature": 0.3}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        resp = requests.post(self.url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        text = data["choices"][0]["message"]["content"]
        logger.info(f"LLM call served by provider=sambanova model={self.model}")
        return text.strip()


class GenericOpenAILLM(LLMProvider):
    """Generic OpenAI-compatible — works with any endpoint (Ollama, LM Studio, vLLM, etc.)."""

    name = "custom_openai"

    def __init__(self):
        self.api_key = os.getenv("CUSTOM_OPENAI_API_KEY", "")
        self.url = os.getenv("CUSTOM_OPENAI_URL", "")
        if not self.url:
            raise ValueError("CUSTOM_OPENAI_URL not set (e.g. http://localhost:11434/v1/chat/completions)")
        self.model = os.getenv("CUSTOM_OPENAI_MODEL", "default")

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": self.model, "messages": messages, "temperature": 0.3, "stream": False}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        resp = requests.post(self.url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        msg = data["choices"][0]["message"]
        text = msg.get("content") or msg.get("reasoning") or ""
        logger.info(f"LLM call served by provider=custom_openai model={self.model}")
        return text.strip()


PROVIDERS = {
    "gemini": GeminiLLM,
    "groq": GroqLLM,
    "openrouter": OpenRouterLLM,
    "9router": NineRouterLLM,
    "cerebras": CerebrasLLM,
    "sambanova": SambaNovaLLM,
    "custom_openai": GenericOpenAILLM,
}


def _get_retry_after(error: Exception) -> float | None:
    resp = getattr(error, "response", None)
    if resp is None or resp.status_code != 429:
        return None
    retry_after = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
    if retry_after:
        try:
            return max(float(retry_after), 1.0)
        except ValueError:
            pass
    return None


def generate_with_retry(llm: LLMProvider, prompt: str, system_prompt: str = "") -> str:
    backoff = GENERATE_INITIAL_BACKOFF_SECONDS
    last_error: Exception | None = None

    for attempt in range(1, GENERATE_MAX_RETRIES + 1):
        try:
            try:
                from search_api.services.llm_traces import traced_llm_generate
                return traced_llm_generate(llm, prompt, system_prompt=system_prompt)
            except ImportError:
                return llm.generate(prompt, system_prompt=system_prompt)
        except Exception as e:
            last_error = e
            retry_after = _get_retry_after(e)
            wait = retry_after if retry_after else backoff
            logger.warning(
                f"LLM generate failed (attempt {attempt}/{GENERATE_MAX_RETRIES}): {e}"
                + (f" | Retry-After: {retry_after}s" if retry_after else "")
            )
            if attempt < GENERATE_MAX_RETRIES:
                time.sleep(wait)
                backoff *= 2

    raise RuntimeError(f"LLM generate failed after {GENERATE_MAX_RETRIES} attempts: {last_error}") from last_error


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    if provider_name is None:
        provider_name = _get_active_provider_from_db()

    cls = PROVIDERS.get(provider_name)
    if cls is None:
        raise ValueError(
            f"Unknown LLM provider '{provider_name}'. "
            f"Available: {list(PROVIDERS.keys())}"
        )
    return cls()


def _get_active_provider_from_db() -> str:
    try:
        from bilingual_etl.load.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value->>'active' FROM app_config WHERE key = 'llm_provider'"
                )
                row = cur.fetchone()
                if row and row[0]:
                    return row[0]
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Could not read LLM provider from DB: {e}. Defaulting to 'gemini'.")
    return "gemini"
