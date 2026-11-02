"""Explicit benchmark-only hosted adapter; the workbench continues to use Ollama."""

import json
import os

from langchain_ollama import ChatOllama

from .agent import MODEL_CONTEXT_TOKENS, _build_model
from .runs import BudgetExceeded


def benchmark_model(provider, model_name, *, base_url=None):
    if provider == "ollama":
        options = {"model_name": model_name, "max_output_tokens": 2048, "provider": "ollama"}
        if base_url is not None:
            options["base_url"] = base_url
        return _build_model(**options)
    if provider != "openai":
        raise ValueError("Unsupported benchmark provider")
    if not os.getenv("OPENAI_API_KEY") or not model_name:
        raise ValueError("Hosted benchmark requires OPENAI_API_KEY and an explicit model")
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise ValueError("Install the optional hosted extra") from exc
    # Pin the official endpoint; never inherit a third-party base URL. No retry
    # can silently multiply admitted requests. No web/tools/remote MCP enabled.
    return ChatOpenAI(
        model=model_name,
        base_url="https://api.openai.com/v1",
        api_key=os.environ["OPENAI_API_KEY"],
        max_tokens=2048,
        timeout=60,
        max_retries=0,
        use_responses_api=False,
        store=False,
    )


def cap_request(request, output_tokens):
    """Apply the admitted output cap to the actual adapter, fail closed otherwise."""
    if isinstance(request.model, ChatOllama):
        return request.override(
            model=request.model.model_copy(update={"num_predict": output_tokens})
        )
    if getattr(request.model, "eil_provider", None) == "vllm":
        # The adapter checks the actual final chat/tools/schema payload with
        # vLLM's local tokenizer. It never downloads an OpenAI tokenizer.
        return request.override(
            model=request.model.model_copy(update={"max_tokens": output_tokens}),
            model_settings={k: v for k, v in request.model_settings.items() if k != "reasoning"},
        )
    from langchain_core.utils.function_calling import convert_to_openai_tool
    from langchain_openai import ChatOpenAI

    if not isinstance(request.model, ChatOpenAI):
        raise ValueError("Unreviewed model adapter")
    messages = ([request.system_message] if request.system_message else []) + request.messages
    # Fixed reservation matches Ollama's context window. Refuse larger hosted
    # prompts, including tool schemas, before sending anything. A margin covers
    # provider framing differences; actual usage remains checked on settlement.
    # The installed ChatOpenAI counter explicitly ignores tool schemas. Count
    # their serialized form separately instead of silently under-reserving.
    count = request.model.get_num_tokens_from_messages(messages, allow_fetching_images=False)
    schemas = [convert_to_openai_tool(tool) for tool in request.tools]
    # Framework output-contract tools are appended after middleware. Include
    # their schemas here too, before reserving/sending the hosted prompt.
    schemas.extend(
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.json_schema,
            },
        }
        for spec in getattr(request.response_format, "schema_specs", [])
    )
    if schemas:
        count += request.model.get_num_tokens(json.dumps(schemas)) + 32 * len(schemas)
    if count + 512 > MODEL_CONTEXT_TOKENS:
        raise BudgetExceeded("Hosted input exceeds the benchmark context envelope", "tokens")
    settings = {k: v for k, v in request.model_settings.items() if k != "reasoning"}
    return request.override(
        model=request.model.model_copy(update={"max_tokens": output_tokens}),
        model_settings=settings,
    )
