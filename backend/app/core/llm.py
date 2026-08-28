"""
Centralized AI model factory.

Provides factory functions for initializing Embeddings and BaseChatModel instances
based on application configuration (`app.core.config.settings`).
Every domain service should import from here instead of directly instantiating
provider-specific client classes.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_embeddings_client(
    provider: str | None = None,
    model: str | None = None,
) -> Embeddings:
    """Return an Embeddings instance configured from settings.

    Args:
        provider: Optional override for EMBEDDING_PROVIDER ('huggingface', 'openai').
        model: Optional override for EMBEDDING_MODEL.
    """
    settings = get_settings()
    active_provider = (provider or settings.EMBEDDING_PROVIDER).lower()
    active_model = model or settings.EMBEDDING_MODEL

    match active_provider:
        case "huggingface":
            from langchain_huggingface import HuggingFaceEndpointEmbeddings

            api_key = settings.HUGGINGFACE_API_KEY or None
            return HuggingFaceEndpointEmbeddings(
                model=active_model,
                huggingfacehub_api_token=api_key,
            )
        case "openai":
            from langchain_openai import OpenAIEmbeddings

            api_key = SecretStr(settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
            return OpenAIEmbeddings(
                api_key=api_key,
                model=active_model,
                dimensions=settings.EMBEDDING_DIMENSIONS,
            )
        case _:
            raise ValueError(
                f"Unsupported EMBEDDING_PROVIDER: '{active_provider}'. Supported options: 'huggingface', 'openai'."
            )


def get_llm_client(
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """Return a BaseChatModel instance configured from settings.

    Args:
        provider: Optional override for LLM_PROVIDER ('huggingface', 'anthropic', 'openai', 'groq').
        model: Optional override for LLM_MODEL.
        temperature: Optional sampling temperature override.
        max_tokens: Optional maximum output tokens override.
        kwargs: Additional model parameters passed directly to the constructor.
    """
    settings = get_settings()
    active_provider = (provider or settings.LLM_PROVIDER).lower()
    active_model = model or settings.LLM_MODEL
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS

    match active_provider:
        case "huggingface":
            from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

            api_key = settings.HUGGINGFACE_API_KEY or None
            endpoint = HuggingFaceEndpoint(  # pyright: ignore[reportCallIssue]
                repo_id=active_model,
                huggingfacehub_api_token=api_key,
                temperature=temp,
                max_new_tokens=tokens,
                **kwargs,
            )
            return ChatHuggingFace(llm=endpoint)

        case "anthropic":
            from langchain_anthropic import ChatAnthropic

            anthropic_key = SecretStr(settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else SecretStr("")
            return ChatAnthropic(
                api_key=anthropic_key,
                model_name=active_model,
                temperature=temp,
                max_tokens_to_sample=tokens,
                **kwargs,
            )

        case "openai":
            from langchain_openai import ChatOpenAI

            openai_key = SecretStr(settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
            return ChatOpenAI(
                api_key=openai_key,
                model=active_model,
                temperature=temp,
                max_completion_tokens=tokens,
                **kwargs,
            )

        case "groq":
            from langchain_groq import ChatGroq

            groq_key = SecretStr(settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
            return ChatGroq(
                api_key=groq_key,
                model=active_model,
                temperature=temp,
                max_tokens=tokens,
                **kwargs,
            )

        case _:
            raise ValueError(
                f"Unsupported LLM_PROVIDER: '{active_provider}'. Supported options: 'huggingface', 'anthropic', 'openai', 'groq'."
            )
