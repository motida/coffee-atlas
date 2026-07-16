"""Google Gemini embedding service using the google-genai SDK."""

import time
from typing import Protocol

from google import genai
from google.genai import errors as genai_errors

from backend.config import settings

MODEL = "gemini-embedding-001"
DIMENSIONS = 3072
BATCH_LIMIT = 50  # Conservative to stay under free-tier 100 req/min
RATE_LIMIT_PAUSE = 60  # Seconds to wait on 429 before retrying
MAX_RETRIES = 3


def vector_param(vector: list[float]) -> str:
    """Serialize an embedding for binding as a DuckDB query parameter.

    The duckdb client's Python-list-to-value transform costs ~170 ms for a
    3072-element vector — dwarfing the queries it feeds. Binding the vector
    as an array-literal string and letting the SQL-side ``::FLOAT[N]`` cast
    parse it is ~100x faster and yields identical values (repr round-trips
    doubles exactly; the cast truncates to float32 either way).
    """
    return "[" + ",".join(map(repr, vector)) + "]"


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class EmbeddingService:
    """Synchronous embedding service backed by Gemini gemini-embedding-001."""

    def __init__(self, api_key: str | None = None):
        self.client = genai.Client(api_key=api_key or settings.GEMINI_API_KEY)

    def embed(self, text: str) -> list[float]:
        """Embed a single text string. Returns a 3072-dim float vector."""
        result = self._call([text])
        return result.embeddings[0].values

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, chunking to stay within API limits.

        Returns vectors in the same order as the input texts.
        Pauses between chunks to avoid rate limits.
        """
        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), BATCH_LIMIT):
            if i > 0:
                time.sleep(2)  # Brief pause between chunks
            chunk = texts[i : i + BATCH_LIMIT]
            result = self._call(chunk)
            all_vectors.extend(emb.values for emb in result.embeddings)
        return all_vectors

    def _call(self, contents: list[str]):
        """Call embed_content with retry on rate-limit errors."""
        for attempt in range(MAX_RETRIES):
            try:
                return self.client.models.embed_content(
                    model=MODEL,
                    contents=contents,
                    config={"output_dimensionality": DIMENSIONS},
                )
            except genai_errors.ClientError as e:
                if "429" in str(e) and attempt < MAX_RETRIES - 1:
                    wait = RATE_LIMIT_PAUSE * (attempt + 1)
                    print(
                        f"  Rate limited, waiting {wait}s (attempt {attempt + 1}/{MAX_RETRIES})..."
                    )
                    time.sleep(wait)
                else:
                    raise
