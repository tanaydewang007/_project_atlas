import httpx
import pytest
from botocore.stub import Stubber

from src.core.config import Settings
from src.services.llm import LLMService


def make(**kwargs) -> LLMService:
    return LLMService(Settings(_env_file=None, **kwargs))


@pytest.mark.parametrize(
    "kwargs, enabled",
    [
        ({}, False),
        ({"llm_provider": "ollama"}, True),
        ({"llm_provider": "openai"}, False),
        ({"llm_provider": "openai", "llm_api_key": "k"}, True),
        ({"llm_provider": "bedrock"}, False),
        ({"llm_provider": "bedrock", "llm_model": "some.model-v1:0"}, True),
        ({"llm_provider": "custom", "llm_model": "m"}, False),
        ({"llm_provider": "custom", "llm_model": "m", "llm_base_url": "http://x/v1"}, True),
    ],
)
def test_provider_enabled_rules(kwargs, enabled):
    assert make(**kwargs).enabled is enabled


def test_ollama_and_gemini_defaults():
    assert make(llm_provider="ollama").base_url == "http://localhost:11434/v1"
    assert make(llm_provider="gemini", llm_api_key="k").model == "gemini-2.5-flash"


def test_bedrock_converse_is_parsed():
    svc = make(llm_provider="bedrock", llm_model="some.model-v1:0", aws_access_key_id="a", aws_secret_access_key="b")
    with Stubber(svc.bedrock_client()) as stub:
        stub.add_response(
            "converse",
            {
                "output": {"message": {"role": "assistant", "content": [{"text": "hello"}]}},
                "stopReason": "end_turn",
                "usage": {"inputTokens": 11, "outputTokens": 3, "totalTokens": 14},
                "metrics": {"latencyMs": 5},
            },
        )
        result = svc.complete("sys", "hi")
    assert (result.text, result.tokens_in, result.tokens_out) == ("hello", 11, 3)


def test_gemini_request_format(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 7, "completion_tokens": 2}})

    real = httpx.Client
    monkeypatch.setattr("src.services.llm.httpx.Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    svc = make(llm_provider="gemini", llm_api_key="secret-key", llm_model="gemini-2.5-flash")
    result = svc.complete("sys", "hello")
    assert seen["url"] == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    assert seen["auth"] == "Bearer secret-key" and '"model":"gemini-2.5-flash"' in seen["body"].replace(" ", "")
    assert (result.text, result.tokens_in, result.tokens_out) == ("hi", 7, 2)


def test_failed_provider_call_raises_unavailable(monkeypatch):
    from src.core.errors import LLMUnavailable

    real = httpx.Client
    monkeypatch.setattr("src.services.llm.httpx.Client", lambda **kw: real(transport=httpx.MockTransport(lambda r: httpx.Response(429)), **kw))
    with pytest.raises(LLMUnavailable):
        make(llm_provider="gemini", llm_api_key="k").complete("s", "u")


def test_each_provider_has_its_own_variables():
    gemini = make(llm_provider="gemini", gemini_api_key="g-key", gemini_model="gem-model")
    assert gemini.enabled and gemini.api_key == "g-key" and gemini.model == "gem-model"
    ollama = make(llm_provider="ollama", ollama_model="qwen", ollama_base_url="http://host:1/v1/")
    assert ollama.enabled and ollama.model == "qwen" and ollama.base_url == "http://host:1/v1"
    bedrock = make(llm_provider="bedrock", bedrock_model="some.model-v1:0")
    assert bedrock.enabled and bedrock.model == "some.model-v1:0"
    assert make(llm_provider="openai", openai_api_key="o", openai_model="m").model == "m"
    assert make(llm_provider="anthropic", anthropic_api_key="a", anthropic_model="m").enabled


def test_provider_variable_wins_over_the_generic_one_and_generic_still_works():
    both = make(llm_provider="gemini", gemini_api_key="own", llm_api_key="generic", gemini_model="own-model", llm_model="generic-model")
    assert both.api_key == "own" and both.model == "own-model"
    only_generic = make(llm_provider="gemini", llm_api_key="generic", llm_model="generic-model")
    assert only_generic.enabled and only_generic.api_key == "generic" and only_generic.model == "generic-model"


def test_other_providers_variables_do_not_leak():
    svc = make(llm_provider="ollama", gemini_api_key="g", gemini_model="gem")
    assert svc.model == "llama3.1" and svc.api_key == ""
