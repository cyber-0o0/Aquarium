from typing import List, Optional
import httpx
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.base_url = base_url or "https://api.proxyapi.ru/openai/v1"
        self.model = "text-embedding-3-small"

    async def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for a single text string using OpenAI-compatible API.
        """
        if not self.api_key:
            logger.error("No API key for embeddings")
            return []

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                # Ensuring base_url ends with v1/ if it doesn't
                url = self.base_url.rstrip('/')
                if not url.endswith('/embeddings'):
                    url = f"{url}/embeddings"

                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "input": text,
                        "model": self.model
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"Embedding API error: {response.status_code} - {response.text}")
                    return []
                
                data = response.json()
                return data["data"][0]["embedding"]
            except Exception as e:
                logger.error(f"Embedding exception: {e}")
                return []

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Simple python implementation of cosine similarity."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = sum(a * a for a in v1) ** 0.5
    magnitude2 = sum(b * b for b in v2) ** 0.5
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
        
    return dot_product / (magnitude1 * magnitude2)
