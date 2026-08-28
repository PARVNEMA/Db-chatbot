"""Unit tests for app.core.llm centralized AI factory."""

from unittest.mock import patch

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import Settings
from app.core.llm import get_embeddings_client, get_llm_client


def test_get_embeddings_client_huggingface() -> None:
    test_settings = Settings(
        EMBEDDING_PROVIDER="huggingface",
        EMBEDDING_MODEL="BAAI/bge-small-en-v1.5",
        HUGGINGFACE_API_KEY="hf_test_token",
    )
    with patch("app.core.llm.get_settings", return_value=test_settings):
        client = get_embeddings_client()
        assert isinstance(client, Embeddings)


def test_get_embeddings_client_openai() -> None:
    test_settings = Settings(
        EMBEDDING_PROVIDER="openai",
        EMBEDDING_MODEL="text-embedding-3-small",
        EMBEDDING_DIMENSIONS=1536,
        OPENAI_API_KEY="sk-test-key",
    )
    with patch("app.core.llm.get_settings", return_value=test_settings):
        client = get_embeddings_client()
        assert isinstance(client, Embeddings)


def test_get_embeddings_client_unsupported() -> None:
    test_settings = Settings(
        EMBEDDING_PROVIDER="unsupported_provider",
    )
    with patch("app.core.llm.get_settings", return_value=test_settings):
        with pytest.raises(ValueError, match="Unsupported EMBEDDING_PROVIDER"):
            get_embeddings_client()


def test_get_llm_client_huggingface() -> None:
    test_settings = Settings(
        LLM_PROVIDER="huggingface",
        LLM_MODEL="mistralai/Mistral-7B-Instruct-v0.3",
        HUGGINGFACE_API_KEY="hf_test_token",
    )
    with patch("app.core.llm.get_settings", return_value=test_settings):
        client = get_llm_client()
        assert isinstance(client, BaseChatModel)


def test_get_llm_client_anthropic() -> None:
    test_settings = Settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-3-5-sonnet-20241022",
        ANTHROPIC_API_KEY="sk-ant-test",
    )
    with patch("app.core.llm.get_settings", return_value=test_settings):
        client = get_llm_client()
        assert isinstance(client, BaseChatModel)


def test_get_llm_client_openai() -> None:
    test_settings = Settings(
        LLM_PROVIDER="openai",
        LLM_MODEL="gpt-4o-mini",
        OPENAI_API_KEY="sk-test-key",
    )
    with patch("app.core.llm.get_settings", return_value=test_settings):
        client = get_llm_client()
        assert isinstance(client, BaseChatModel)


def test_get_llm_client_groq() -> None:
    test_settings = Settings(
        LLM_PROVIDER="groq",
        LLM_MODEL="llama-3.3-70b-versatile",
        GROQ_API_KEY="gsk-test-key",
    )
    with patch("app.core.llm.get_settings", return_value=test_settings):
        client = get_llm_client()
        assert isinstance(client, BaseChatModel)


def test_get_llm_client_unsupported() -> None:
    test_settings = Settings(
        LLM_PROVIDER="unsupported_llm",
    )
    with patch("app.core.llm.get_settings", return_value=test_settings):
        with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER"):
            get_llm_client()
