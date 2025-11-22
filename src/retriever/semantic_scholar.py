"""Semantic Scholar API retriever for citation data."""
from typing import Optional
import httpx
from src.config.cache import RedisCache
from src.config.logging import get_logger

logger = get_logger(__name__)


class SemanticScholarRetriever:
    """Retriever for Semantic Scholar citation data."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, cache: RedisCache, api_key: Optional[str] = None):
        """Initialize Semantic Scholar retriever.

        Args:
            cache: Redis cache instance
            api_key: Optional S2 API key for higher rate limits
        """
        self.cache = cache
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["x-api-key"] = api_key

    async def get_paper_citations(self, arxiv_id: str) -> Optional[dict]:
        """Get citation count and influential citation count.

        Args:
            arxiv_id: arXiv paper ID

        Returns:
            Dict with citation data or None
        """
        try:
            async with httpx.AsyncClient() as client:
                # Query by arXiv ID
                url = f"{self.BASE_URL}/paper/arXiv:{arxiv_id}"
                params = {"fields": "title,citationCount,influentialCitationCount,publicationDate"}

                logger.info("s2_api_fetch", arxiv_id=arxiv_id)
                response = await client.get(url, params=params, headers=self.headers, timeout=10.0)

                if response.status_code == 404:
                    logger.warning("s2_not_found", arxiv_id=arxiv_id)
                    return None

                response.raise_for_status()
                data = response.json()

                citation_data = {
                    "arxiv_id": arxiv_id,
                    "citation_count": data.get("citationCount", 0),
                    "influential_citation_count": data.get("influentialCitationCount", 0),
                    "publication_date": data.get("publicationDate"),
                }

                logger.info(
                    "s2_fetched",
                    arxiv_id=arxiv_id,
                    citations=citation_data["citation_count"]
                )

                return citation_data

        except httpx.HTTPStatusError as e:
            logger.error("s2_http_error", arxiv_id=arxiv_id, status=e.response.status_code)
            return None
        except Exception as e:
            logger.error("s2_fetch_error", arxiv_id=arxiv_id, error=str(e))
            return None

    async def get_citations_batch(self, arxiv_ids: list[str]) -> dict[str, Optional[dict]]:
        """Get citation data for multiple papers.

        Args:
            arxiv_ids: List of arXiv IDs

        Returns:
            Dict mapping arxiv_id to citation data
        """
        results = {}
        for arxiv_id in arxiv_ids:
            results[arxiv_id] = await self.get_paper_citations(arxiv_id)
        return results
