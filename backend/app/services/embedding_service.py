"""
Embedding Service.
Generates vector embeddings from text using OpenAI or local models.
"""
import asyncio
from typing import List, Optional
from functools import lru_cache

import openai

# Make sentence_transformers optional
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    from backend.app.config import settings
except ImportError:
    from app.config import settings


class EmbeddingService:
    """Service for generating text embeddings."""
    
    def __init__(self, provider: str = settings.EMBEDDING_PROVIDER):
        self.provider = provider
        self._openai_client = None
        self._local_model = None
        
        if provider == "openai":
            self._init_openai()
        elif provider == "local":
            self._init_local()
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")
    
    def _init_openai(self):
        """Initialize OpenAI client."""
        # Use configured API key or fallback to a dummy key during testing/mocking
        api_key = settings.OPENAI_API_KEY or "dummy-key-for-testing"
        self._openai_client = openai.AsyncOpenAI(api_key=api_key)
    
    def _init_local(self):
        """Initialize local sentence-transformers model."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install it with: pip install sentence-transformers"
            )
        self._local_model = SentenceTransformer(settings.LOCAL_EMBEDDING_MODEL)
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for the given text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        normalized_text = self._normalize_text(text)
        
        if self.provider == "openai":
            return await self._generate_openai_embedding(normalized_text)
        elif self.provider == "local":
            return await self._generate_local_embedding(normalized_text)
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.
        More efficient than calling generate_embedding() repeatedly.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        normalized_texts = [self._normalize_text(t) for t in texts]
        
        if self.provider == "openai":
            return await self._generate_openai_embeddings_batch(normalized_texts)
        elif self.provider == "local":
            return await self._generate_local_embeddings_batch(normalized_texts)
    
    async def _generate_openai_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI API."""
        if not settings.OPENAI_API_KEY and getattr(self._openai_client, "api_key", None) == "dummy-key-for-testing":
            raise ValueError("OPENAI_API_KEY not set")
        response = await self._openai_client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=text
        )
        return response.data[0].embedding
    
    async def _generate_openai_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings in batch using OpenAI API."""
        if not settings.OPENAI_API_KEY and getattr(self._openai_client, "api_key", None) == "dummy-key-for-testing":
            raise ValueError("OPENAI_API_KEY not set")
        response = await self._openai_client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=texts
        )
        return [item.embedding for item in response.data]
    
    async def _generate_local_embedding(self, text: str) -> List[float]:
        """Generate embedding using local sentence-transformers model."""
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None, 
            lambda: self._local_model.encode(text, convert_to_numpy=True)
        )
        vec = embedding.tolist()
        # Ensure dimension matches Vector(1536) in PostgreSQL pgvector
        if len(vec) < 1536:
            vec = vec + [0.0] * (1536 - len(vec))
        elif len(vec) > 1536:
            vec = vec[:1536]
        return vec
    
    async def _generate_local_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings in batch using local model."""
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self._local_model.encode(texts, convert_to_numpy=True)
        )
        res = []
        for emb in embeddings.tolist():
            if len(emb) < 1536:
                emb = emb + [0.0] * (1536 - len(emb))
            elif len(emb) > 1536:
                emb = emb[:1536]
            res.append(emb)
        return res
    
    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalize text before embedding.
        - Strip whitespace
        - Convert to lowercase (optional, depends on use case)
        - Remove extra newlines
        """
        text = text.strip()
        text = " ".join(text.split())  # Collapse multiple spaces/newlines
        return text
    
    def get_dimension(self) -> int:
        """
        Get the embedding dimension for the current provider.
        
        Returns the configured dimension (which may involve padding for local models).
        """
        if self.provider == "openai":
            return settings.EMBEDDING_DIMENSION
        elif self.provider == "local":
            # Local embeddings are padded to 1536 to match vector storage dimension
            return 1536


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Get singleton embedding service instance."""
    return EmbeddingService()
