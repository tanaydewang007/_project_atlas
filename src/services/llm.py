from dataclasses import dataclass

import boto3
import httpx
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from src.core.config import Settings
from src.core.errors import LLMUnavailable

DEFAULTS = {
    "anthropic": ("https://api.anthropic.com/v1", "claude-haiku-5-5"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash"),
    "ollama": ("http://localhost:11434/v1", "llama3.1"),
    "bedrock": ("", ""),
    "custom": ("", ""),
}


@dataclass
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int


@dataclass
class UsageMeter:
    cap: int
    tokens_in: int = 0
    tokens_out: int = 0

    def add(self, result: LLMResult) -> None:
        self.tokens_in += result.tokens_in
        self.tokens_out += result.tokens_out

    @property
    def exhausted(self) -> bool:
        return self.tokens_in + self.tokens_out >= self.cap


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.provider = settings.llm_provider
        base, model = DEFAULTS.get(self.provider, ("", ""))
        own_key, own_model, own_base = {
            "bedrock": ("", settings.bedrock_model, ""),
            "gemini": (settings.gemini_api_key, settings.gemini_model, ""),
            "ollama": ("", settings.ollama_model, settings.ollama_base_url),
            "openai": (settings.openai_api_key, settings.openai_model, ""),
            "anthropic": (settings.anthropic_api_key, settings.anthropic_model, ""),
        }.get(self.provider, ("", "", ""))
        self.api_key = own_key or settings.llm_api_key
        self.model = own_model or settings.llm_model or model
        self.base_url = (own_base or settings.llm_base_url or base).rstrip("/")
        self._bedrock = None

    @property
    def enabled(self) -> bool:
        if self.provider == "none":
            return False
        if self.provider == "ollama":
            return True
        if self.provider == "bedrock":
            return bool(self.model)
        if self.provider == "custom":
            return bool(self.base_url and self.model)
        return bool(self.api_key)

    def cost(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * self.settings.llm_price_in_per_m + tokens_out * self.settings.llm_price_out_per_m) / 1_000_000

    def complete(self, system: str, user: str) -> LLMResult:
        if not self.enabled:
            raise LLMUnavailable("no LLM configured")
        try:
            if self.provider == "bedrock":
                return self._bedrock_converse(system, user)
            with httpx.Client(timeout=self.settings.llm_timeout_s) as client:
                if self.provider == "anthropic":
                    return self._anthropic(client, system, user)
                return self._openai_compatible(client, system, user)
        except (httpx.HTTPError, BotoCoreError, ClientError, KeyError, IndexError, ValueError) as exc:
            raise LLMUnavailable(str(exc)) from exc

    def _anthropic(self, client: httpx.Client, system: str, user: str) -> LLMResult:
        resp = client.post(
            f"{self.base_url}/messages",
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            json={
                "model": self.model,
                "max_tokens": self.settings.llm_max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return LLMResult(data["content"][0]["text"], data["usage"]["input_tokens"], data["usage"]["output_tokens"])

    def _openai_compatible(self, client: httpx.Client, system: str, user: str) -> LLMResult:
        resp = client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            json={
                "model": self.model,
                "max_tokens": self.settings.llm_max_tokens,
                "temperature": 0,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        return LLMResult(data["choices"][0]["message"]["content"], usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

    def bedrock_client(self):
        if self._bedrock is None:
            keys = {}
            if self.settings.aws_access_key_id and self.settings.aws_secret_access_key:
                keys = {
                    "aws_access_key_id": self.settings.aws_access_key_id,
                    "aws_secret_access_key": self.settings.aws_secret_access_key,
                    "aws_session_token": self.settings.aws_session_token or None,
                }
            self._bedrock = boto3.client(
                "bedrock-runtime",
                region_name=self.settings.aws_region,
                config=Config(connect_timeout=5, read_timeout=self.settings.llm_timeout_s, retries={"max_attempts": 1}),
                **keys,
            )
        return self._bedrock

    def _bedrock_converse(self, system: str, user: str) -> LLMResult:
        resp = self.bedrock_client().converse(
            modelId=self.model,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": self.settings.llm_max_tokens, "temperature": 0},
        )
        usage = resp["usage"]
        return LLMResult(resp["output"]["message"]["content"][0]["text"], usage["inputTokens"], usage["outputTokens"])
