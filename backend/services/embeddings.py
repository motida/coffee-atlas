"""OpenAI embedding generation service."""

from backend.config import settings


class EmbeddingService:
    def __init__(self):
        self.model = "text-embedding-3-small"
        self.dimensions = 1536

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.embeddings.create(input=text, model=self.model)
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.embeddings.create(input=texts, model=self.model)
        return [item.embedding for item in response.data]
