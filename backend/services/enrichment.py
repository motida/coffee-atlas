"""LLM-based entity extraction and enrichment service."""

from typing import Any


class EnrichmentService:
    async def extract_entities(self, text: str) -> dict[str, Any]:
        """Extract coffee-domain entities from unstructured text."""
        # TODO: Use OpenAI / Claude to extract varieties, origins, flavors, etc.
        raise NotImplementedError

    async def enrich_variety(self, name: str) -> dict[str, Any]:
        """Enrich a variety with additional information from LLM knowledge."""
        # TODO: Generate description, flavor notes, growing conditions
        raise NotImplementedError
