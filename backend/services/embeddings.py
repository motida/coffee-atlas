"""Google Gemini embedding generation service."""

from backend.config import settings


class EmbeddingService:
    def __init__(self):
        self.model = "models/text-embedding-004"
        self.dimensions = 768

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text."""
        import google.generativeai as genai

        genai.configure(api_key=settings.GEMINI_API_KEY)
        result = genai.embed_content(model=self.model, content=text)
        return result["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        import google.generativeai as genai

        genai.configure(api_key=settings.GEMINI_API_KEY)
        results = []
        for text in texts:
            result = genai.embed_content(model=self.model, content=text)
            results.append(result["embedding"])
        return results
