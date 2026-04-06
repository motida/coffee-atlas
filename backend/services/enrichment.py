"""LLM-based entity extraction and enrichment service."""


class EnrichmentService:
    async def extract_entities(self, text: str) -> dict:
        """Extract coffee-domain entities from unstructured text."""
        # TODO: Use OpenAI / Claude to extract varieties, origins, flavors, etc.
        raise NotImplementedError

    async def enrich_variety(self, name: str) -> dict:
        """Enrich a variety with additional information from LLM knowledge."""
        # TODO: Generate description, flavor notes, growing conditions
        raise NotImplementedError
