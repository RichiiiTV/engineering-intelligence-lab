"""Explicit self-hosted vLLM transport; no cloud fallback or agent-selected endpoint.

The operator attests a local weight snapshot revision. `/models` verifies the
served alias, not the server's internals; native launch scripts must enforce local
weights, offline operation and reviewed code. Credentials never enter run state.
"""

import json
import os
import re
from urllib.parse import urlsplit

import httpx

from .agent import MODEL_CONTEXT_TOKENS, ModelUnavailableError

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

MAX_BYTES = 2 * 1024**2
MAX_REQUEST_BYTES = 8 * 1024**2


def checked_config(base_url, model_name, revision):
    try:
        url = urlsplit(base_url)
        valid = (
            url.scheme == "http"
            and url.hostname in {"localhost", "127.0.0.1", "::1"}
            and url.path in {"/v1", "/v1/"}
            and not (url.username or url.password or url.query or url.fragment)
            and (url.port is None or 1 <= url.port <= 65535)
        )
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ModelUnavailableError(
            "vLLM requires an operator-configured plain loopback /v1 endpoint"
        )
    if not isinstance(model_name, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,100}", model_name):
        raise ModelUnavailableError("Configure an explicit vLLM served model alias")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{64}", revision):
        raise ModelUnavailableError("vLLM requires the reviewed local snapshot SHA-256 revision")
    return base_url.rstrip("/")


def api_key(embedding=False):
    key = (os.getenv("EIL_VLLM_EMBEDDING_API_KEY") if embedding else None) or os.getenv(
        "EIL_VLLM_API_KEY"
    )
    if not key or "\r" in key or "\n" in key:
        raise ModelUnavailableError(
            "Set the vLLM API key in the operator environment; no default credential is provided"
        )
    return key


class _BoundedStream(httpx.SyncByteStream):
    def __init__(self, stream):
        self.stream = stream

    def __iter__(self):
        count = 0
        for chunk in self.stream:
            count += len(chunk)
            if count > MAX_BYTES:
                raise ModelUnavailableError("vLLM response exceeded its byte limit")
            yield chunk

    def close(self):
        self.stream.close()


class _BoundedAsyncStream(httpx.AsyncByteStream):
    def __init__(self, stream):
        self.stream = stream

    async def __aiter__(self):
        count = 0
        async for chunk in self.stream:
            count += len(chunk)
            if count > MAX_BYTES:
                raise ModelUnavailableError("vLLM response exceeded its byte limit")
            yield chunk

    async def aclose(self):
        await self.stream.aclose()


class BoundedTransport(httpx.BaseTransport):
    def __init__(self, inner=None):
        self.inner = inner or httpx.HTTPTransport(retries=0)

    def handle_request(self, request):
        response = self.inner.handle_request(request)
        if response.headers.get("Content-Encoding", "identity").lower() not in {"", "identity"}:
            response.close()
            raise ModelUnavailableError("Compressed vLLM responses are not permitted")
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            stream=_BoundedStream(response.stream),
            extensions=response.extensions,
        )

    def close(self):
        self.inner.close()


class BoundedAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner=None):
        self.inner = inner or httpx.AsyncHTTPTransport(retries=0)

    async def handle_async_request(self, request):
        response = await self.inner.handle_async_request(request)
        if response.headers.get("Content-Encoding", "identity").lower() not in {"", "identity"}:
            await response.aclose()
            raise ModelUnavailableError("Compressed vLLM responses are not permitted")
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            stream=_BoundedAsyncStream(response.stream),
            extensions=response.extensions,
        )

    async def aclose(self):
        await self.inner.aclose()


def client(*, embedding=False, timeout=10):
    return httpx.Client(
        timeout=timeout,
        trust_env=False,
        follow_redirects=False,
        headers={"Authorization": "Bearer " + api_key(embedding)},
        transport=BoundedTransport(),
    )


def bounded_json(response):
    response.raise_for_status()
    content = bytearray()
    for part in response.iter_bytes():
        content.extend(part)
        if len(content) > MAX_BYTES:
            raise ModelUnavailableError("vLLM response exceeded its byte limit")
    return json.loads(content)


def verify_model(base_url, model_name, revision, *, embedding=False):
    base_url = checked_config(base_url, model_name, revision)
    try:
        with client(embedding=embedding) as http:
            with http.stream("GET", base_url + "/models") as response:
                models = bounded_json(response)["data"]
        if not isinstance(models, list) or not any(
            isinstance(item, dict) and item.get("id") == model_name for item in models
        ):
            raise ValueError("Configured alias is not served")
        return {"name": model_name, "digest": revision, "provider": "vllm"}
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        raise ModelUnavailableError(
            "The attested vLLM model alias is unavailable; no prompt was sent"
        ) from exc


def json_schema(schema):
    return {
        "type": "json_schema",
        "json_schema": {"name": "eil_response", "schema": schema, "strict": True},
    }


def is_provider_error(exc):
    if ChatOpenAI is None:
        return False
    from openai import APIError

    return isinstance(exc, APIError)


class VLLMChatOpenAI(ChatOpenAI if ChatOpenAI is not None else object):
    """Use LangChain's tool/usage implementation with vLLM's local tokenizer guard."""

    eil_revision: str = ""
    eil_provider: str = "vllm"
    eil_vision: bool = False

    def bind(self, **kwargs):
        if "format" in kwargs:
            kwargs["response_format"] = json_schema(kwargs.pop("format"))
        kwargs.pop("reasoning", None)
        return super().bind(**kwargs)

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        kwargs.pop("reasoning", None)
        if "format" in kwargs:
            kwargs["response_format"] = json_schema(kwargs.pop("format"))
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        base_url = checked_config(self.openai_api_base, self.model_name, self.eil_revision)
        max_tokens = payload.get("max_completion_tokens", payload.get("max_tokens"))
        if (
            not isinstance(max_tokens, int)
            or isinstance(max_tokens, bool)
            or not 1 <= max_tokens <= 2048
        ):
            raise ModelUnavailableError("vLLM requires an admitted output token cap")
        if len(json.dumps(payload).encode("utf-8")) > MAX_REQUEST_BYTES:
            raise ModelUnavailableError("vLLM request exceeded its byte limit")
        for message in payload.get("messages", []):
            content = message.get("content")
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict) or part.get("type") not in {"text", "image_url"}:
                        raise ModelUnavailableError(
                            "Unreviewed vLLM media content is not permitted"
                        )
                    if part.get("type") == "image_url":
                        image = part.get("image_url", {})
                        url = image.get("url", "") if isinstance(image, dict) else image
                        if not self.eil_vision or not str(url).startswith(
                            "data:image/jpeg;base64,"
                        ):
                            raise ModelUnavailableError(
                                "Only normalized local images with reviewed vision support are permitted"
                            )
        verify_model(base_url, self.model_name, self.eil_revision)
        tokenize = {
            "model": self.model_name,
            "messages": payload["messages"],
            "add_generation_prompt": True,
            "return_token_strs": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        for name in ("tools", "response_format"):
            if name in payload:
                tokenize[name] = payload[name]
        try:
            with client() as http:
                with http.stream(
                    "POST", base_url.removesuffix("/v1") + "/tokenize", json=tokenize
                ) as response:
                    counts = bounded_json(response)
            count = counts["count"]
            ceiling = counts.get("max_model_len", MODEL_CONTEXT_TOKENS)
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError("Invalid local token count")
            if not isinstance(ceiling, int) or isinstance(ceiling, bool) or ceiling < 1:
                raise ValueError("Invalid local context size")
            if count + max_tokens > min(ceiling, MODEL_CONTEXT_TOKENS):
                from .runs import BudgetExceeded

                raise BudgetExceeded(
                    "vLLM input and output exceed the run context envelope", "tokens"
                )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ModelUnavailableError(
                "vLLM local tokenization failed; generation was not sent"
            ) from exc
        # No image URLs, remote tokenizers, implicit retries or provider fallback.
        return payload


def build_model(base_url, model_name, revision, *, max_output_tokens=1024, vision=False):
    checked_config(base_url, model_name, revision)
    verify_model(base_url, model_name, revision)
    if ChatOpenAI is None:
        raise ModelUnavailableError("Install the optional inference extra for vLLM")
    return VLLMChatOpenAI(
        model=model_name,
        base_url=base_url.rstrip("/"),
        api_key=api_key(),
        eil_revision=revision,
        eil_vision=vision,
        temperature=0,
        max_tokens=max_output_tokens or 1024,
        max_retries=0,
        timeout=60,
        use_responses_api=False,
        openai_proxy="",
        store=False,
        disable_streaming=True,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        http_client=httpx.Client(
            timeout=60, trust_env=False, follow_redirects=False, transport=BoundedTransport()
        ),
        http_async_client=httpx.AsyncClient(
            timeout=60, trust_env=False, follow_redirects=False, transport=BoundedAsyncTransport()
        ),
    )


def embedding_vectors(config, texts):
    input_format = config.get("input_format", "plain")
    if input_format not in {"plain", "qwen3"}:
        raise ModelUnavailableError("Unreviewed embedding input format")
    if input_format == "qwen3":
        prefix = "task: search result | query: "
        texts = [
            "Instruct: Retrieve relevant machine documentation passages that answer the question.\nQuery: "
            + text.removeprefix(prefix)
            if text.startswith(prefix)
            else text
            for text in texts
        ]
    verify_model(config["base_url"], config["model_name"], config["revision"], embedding=True)
    try:
        with client(embedding=True, timeout=30) as http:
            with http.stream(
                "POST",
                config["base_url"].rstrip("/") + "/embeddings",
                json={
                    "model": config["model_name"],
                    "input": texts,
                    "encoding_format": "float",
                },
            ) as response:
                data = bounded_json(response)
        records = data["data"]
        if (
            not isinstance(records, list)
            or any(
                not isinstance(item, dict) or type(item.get("index")) is not int for item in records
            )
            or len(records) != len(texts)
            or sorted(item["index"] for item in records) != list(range(len(texts)))
        ):
            raise ValueError("Embedding indices mismatch")
        vectors = [item["embedding"] for item in sorted(records, key=lambda item: item["index"])]
        return (
            "vllm:"
            + config["model_name"]
            + "@sha256:"
            + config["revision"]
            + ("|qwen3-input-v1" if input_format == "qwen3" else ""),
            vectors,
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise ModelUnavailableError("vLLM embeddings are unavailable") from exc
