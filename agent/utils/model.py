from typing import Literal, TypedDict, Unpack

from langchain.chat_models import init_chat_model

OPENAI_RESPONSES_WS_BASE_URL = "wss://api.openai.com/v1"

# Anthropic SDK default is 2; a 529 burst can outlive that. Bump to give the
# primary provider a fair chance before the fallback middleware kicks in.
DEFAULT_MAX_RETRIES = 6


OpenAIReasoningEffort = Literal["none", "low", "medium", "high", "xhigh"]


class OpenAIReasoning(TypedDict, total=False):
    effort: OpenAIReasoningEffort


class ModelKwargs(TypedDict, total=False):
    max_tokens: int | None
    reasoning: OpenAIReasoning | None
    temperature: float | None
    max_retries: int | None


def make_model(model_id: str, **kwargs: Unpack[ModelKwargs]):
    if not model_id.startswith("openai:"):
        raise ValueError("Only OpenAI models are supported. Set LLM_MODEL_ID to openai:<model>")
    model_kwargs: dict[str, object] = kwargs.copy()
    model_kwargs.setdefault("max_retries", DEFAULT_MAX_RETRIES)

    model_kwargs["base_url"] = OPENAI_RESPONSES_WS_BASE_URL
    model_kwargs["use_responses_api"] = True

    return init_chat_model(model=model_id, **model_kwargs)


def fallback_model_id_for(primary_model_id: str) -> str | None:
    """Open SWE SDD runtime does not use cross-provider fallback routing."""
    _ = primary_model_id
    return None
