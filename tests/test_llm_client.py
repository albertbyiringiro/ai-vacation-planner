from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.llm.anthropic_client import AnthropicLLMClient, build_llm_client
from app.llm.client import LLMClient, Message
from app.settings import Settings


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.calls: list[dict] = []

    def create(self, **params):
        self.calls.append(params)
        return self.response


def make_response(text="pong", blocks=None):
    content = (
        blocks if blocks is not None else [SimpleNamespace(type="text", text=text)]
    )
    return SimpleNamespace(
        content=content,
        model="claude-test",
        stop_reason="end_turn",
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=3,
            cache_read_input_tokens=None,
            cache_creation_input_tokens=None,
            output_tokens_details=SimpleNamespace(thinking_tokens=1),
        ),
        _request_id="req_test",
    )


def make_client(response=None):
    messages = FakeMessages(response or make_response())
    sdk = SimpleNamespace(messages=messages)
    return AnthropicLLMClient(sdk, default_model="default-model"), messages


def test_client_satisfies_the_protocol():
    client, _ = make_client()
    assert isinstance(client, LLMClient)


def test_complete_maps_the_response():
    client, _ = make_client()
    r = client.complete([Message("user", "ping")])
    assert r.text == "pong"
    assert r.model == "claude-test"
    assert r.stop_reason == "end_turn"
    assert r.request_id == "req_test"
    assert r.usage.input_tokens == 10
    assert r.usage.output_tokens == 3
    assert r.usage.cache_read_input_tokens == 0  # None from the SDK becomes 0
    assert r.usage.thinking_tokens == 1


def test_complete_sends_only_what_was_asked_for():
    client, messages = make_client()
    client.complete([Message("user", "hi")])
    assert messages.calls == [
        {
            "model": "default-model",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "hi"}],
        }
    ]


def test_system_effort_and_model_override_are_passed_through():
    client, messages = make_client()
    client.complete(
        [Message("user", "hi")],
        system="be brief",
        effort="low",
        model="other",
        max_tokens=50,
    )
    sent = messages.calls[0]
    assert sent["system"] == "be brief"
    assert sent["output_config"] == {"effort": "low"}
    assert sent["model"] == "other"
    assert sent["max_tokens"] == 50


def test_non_text_blocks_are_ignored():
    blocks = [
        SimpleNamespace(type="thinking", thinking="hmm"),
        SimpleNamespace(type="text", text="answer"),
    ]
    client, _ = make_client(make_response(blocks=blocks))
    assert client.complete([Message("user", "hi")]).text == "answer"


def test_repr_does_not_leak_the_sdk_or_key():
    sdk = SimpleNamespace(messages=None, api_key="sk-ant-secret")
    client = AnthropicLLMClient(sdk, default_model="m")
    assert "sk-ant-secret" not in repr(client)


def settings(**overrides) -> Settings:
    return Settings(_env_file=None, jwt_secret="x" * 32, **overrides)


def test_build_requires_an_api_key():
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        build_llm_client(settings())


def test_build_applies_model_timeout_and_retries():
    client = build_llm_client(
        settings(
            anthropic_api_key="sk-ant-test",
            llm_model="m1",
            llm_timeout_seconds=12,
            llm_max_retries=4,
        )
    )
    assert client.default_model == "m1"
    assert client._sdk.timeout == 12
    assert client._sdk.max_retries == 4


@pytest.mark.parametrize(
    "bad",
    [
        {"llm_timeout_seconds": 0},
        {"llm_timeout_seconds": 301},
        {"llm_max_retries": -1},
        {"llm_max_retries": 6},
        {"llm_model": ""},
    ],
)
def test_settings_reject_out_of_range_llm_values(bad):
    with pytest.raises(ValidationError):
        settings(**bad)
