"""
Embedding Service Tests.
"""
import pytest

try:
    from backend.app.services.embedding_service import EmbeddingService, get_embedding_service
except ImportError:
    from app.services.embedding_service import EmbeddingService, get_embedding_service


@pytest.mark.asyncio
async def test_local_embedding_generation():
    """Test local embedding generation."""
    service = EmbeddingService(provider="local")
    embedding = await service.generate_embedding("Test text")
    
    assert len(embedding) > 0
    assert all(isinstance(x, float) for x in embedding)


def test_text_normalization():
    """Test text normalization."""
    service = EmbeddingService(provider="local")
    
    # Test whitespace collapsing
    normalized = service._normalize_text("  Multiple   spaces   ")
    assert normalized == "Multiple spaces"
    
    # Test newline handling
    normalized = service._normalize_text("Line 1\n\nLine 2\n\n\nLine 3")
    assert "\n" not in normalized


def test_get_dimension():
    """Test getting embedding dimension."""
    # Project uses local embeddings which are padded to 1536
    service_local = EmbeddingService(provider="local")
    assert service_local.get_dimension() == 1536


def test_singleton_get_embedding_service():
    """Test get_embedding_service singleton behavior."""
    service1 = get_embedding_service()
    service2 = get_embedding_service()
    assert service1 is service2
