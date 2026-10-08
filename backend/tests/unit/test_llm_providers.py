"""
LLM Provider Tests.
Validates that Gemini and Groq providers implement the base interface correctly.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.app.services.llm.base import BaseLLMProvider, LLMResponse
from backend.app.services.llm.gemini_provider import GeminiProvider
from backend.app.services.llm.groq_provider import GroqProvider


@pytest.mark.asyncio
@patch("backend.app.services.llm.gemini_provider.genai")
async def test_gemini_provider_generate(mock_genai):
    """Test Gemini provider generates responses."""
    # Create mock usage metadata
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 15
    mock_usage.candidates_token_count = 8
    mock_usage.total_token_count = 23
    
    # Create mock response with text property
    mock_response = MagicMock()
    mock_response.text = "Gemini response"
    mock_response.usage_metadata = mock_usage
    
    # Setup mock model
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
    mock_genai.GenerativeModel.return_value = mock_model
    
    provider = GeminiProvider(api_key="test-key")
    response = await provider.generate(prompt="Test prompt", model="gemini-1.5-flash")
    
    assert isinstance(response, LLMResponse)
    assert response.content == "Gemini response"
    assert response.provider == "gemini"
    assert response.total_tokens == 23
    assert response.input_tokens == 15
    assert response.output_tokens == 8


@pytest.mark.asyncio
@patch("backend.app.services.llm.groq_provider.AsyncGroq")
async def test_groq_provider_generate(mock_client_class):
    """Test Groq provider generates responses."""
    # Create mock response
    mock_message = MagicMock()
    mock_message.content = "Groq response"
    
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 12
    mock_usage.completion_tokens = 6
    mock_usage.total_tokens = 18
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.model = "llama-3.3-70b-versatile"
    mock_response.usage = mock_usage
    
    # Setup mock client
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_client_class.return_value = mock_client
    
    provider = GroqProvider(api_key="test-key")
    response = await provider.generate(prompt="Test prompt", model="llama-3.3-70b-versatile")
    
    assert isinstance(response, LLMResponse)
    assert response.content == "Groq response"
    assert response.provider == "groq"
    assert response.total_tokens == 18
    assert response.input_tokens == 12
    assert response.output_tokens == 6


def test_all_providers_implement_base():
    """Test all providers implement BaseLLMProvider interface."""
    providers = [GeminiProvider, GroqProvider]
    
    for ProviderClass in providers:
        assert issubclass(ProviderClass, BaseLLMProvider)
        assert hasattr(ProviderClass, 'generate')
        assert hasattr(ProviderClass, 'get_default_model')


def test_all_providers_have_default_models():
    """Test all providers return valid default models."""
    providers = [
        (GeminiProvider, "test-key-gemini"),
        (GroqProvider, "test-key-groq")
    ]
    
    for ProviderClass, api_key in providers:
        provider = ProviderClass(api_key=api_key)
        default_model = provider.get_default_model()
        assert default_model is not None
        assert isinstance(default_model, str)
        assert len(default_model) > 0


@pytest.mark.asyncio
async def test_llm_response_dataclass():
    """Test LLMResponse dataclass structure."""
    response = LLMResponse(
        content="Test content",
        model="test-model",
        provider="test-provider",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        latency_ms=250,
        estimated_cost=0.0005
    )
    
    assert response.content == "Test content"
    assert response.model == "test-model"
    assert response.provider == "test-provider"
    assert response.input_tokens == 100
    assert response.output_tokens == 50
    assert response.total_tokens == 150
    assert response.latency_ms == 250
    assert response.estimated_cost == 0.0005
