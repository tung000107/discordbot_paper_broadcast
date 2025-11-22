"""arXiv API retriever with caching."""
import re
from typing import Optional
from datetime import datetime
import arxiv
from src.config.cache import RedisCache
from src.config.logging import get_logger

logger = get_logger(__name__)


class ArxivRetriever:
    """Retriever for arXiv papers with Redis caching."""

    # Regex patterns for arXiv ID extraction
    ARXIV_ID_PATTERN = re.compile(r'(?:arxiv\.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5}(?:v\d+)?)', re.IGNORECASE)

    def __init__(self, cache: RedisCache):
        """Initialize arXiv retriever.

        Args:
            cache: Redis cache instance
        """
        self.cache = cache
        self.client = arxiv.Client()

    @classmethod
    def extract_arxiv_ids(cls, text: str) -> list[str]:
        """Extract arXiv IDs from text.

        Args:
            text: Input text containing arXiv links or IDs

        Returns:
            List of extracted arXiv IDs
        """
        matches = cls.ARXIV_ID_PATTERN.findall(text)
        # Remove version suffix for normalization but keep original
        ids = []
        for match in matches:
            # Strip version for uniqueness check
            base_id = re.sub(r'v\d+$', '', match)
            if base_id not in [re.sub(r'v\d+$', '', i) for i in ids]:
                ids.append(match)
        return ids

    async def get_paper(self, arxiv_id: str) -> Optional[dict]:
        """Retrieve paper metadata from arXiv.

        Implements caching per TDS §4.2 contract.

        Args:
            arxiv_id: arXiv paper ID (e.g., "2401.01234" or "2401.01234v2")

        Returns:
            Paper metadata dict or None if not found
        """
        # Normalize ID (remove version for cache key)
        base_id = re.sub(r'v\d+$', '', arxiv_id)

        # Check cache first
        cached = await self.cache.get_paper_metadata(base_id)
        if cached:
            logger.info("arxiv_cache_hit", arxiv_id=base_id)
            return cached

        # Fetch from arXiv API
        try:
            logger.info("arxiv_api_fetch", arxiv_id=arxiv_id)
            search = arxiv.Search(id_list=[arxiv_id], max_results=1)
            results = list(self.client.results(search))

            if not results:
                logger.warning("arxiv_not_found", arxiv_id=arxiv_id)
                return None

            paper = results[0]

            # Format according to TDS §4.2
            metadata = {
                "arxiv_id": paper.entry_id.split('/')[-1],  # Extract ID from URL
                "title": paper.title,
                "authors": [author.name for author in paper.authors],
                "primary_category": paper.primary_category,
                "published": paper.published.isoformat(),
                "abstract": paper.summary.replace('\n', ' ').strip(),
                "pdf_url": paper.pdf_url,
                "entry_url": paper.entry_id,
            }

            # Cache the result
            await self.cache.set_paper_metadata(base_id, metadata)
            logger.info("arxiv_fetched", arxiv_id=base_id, title=paper.title[:50])

            return metadata

        except Exception as e:
            logger.error("arxiv_fetch_error", arxiv_id=arxiv_id, error=str(e))
            return None

    async def get_papers_batch(self, arxiv_ids: list[str]) -> dict[str, Optional[dict]]:
        """Retrieve multiple papers.

        Args:
            arxiv_ids: List of arXiv IDs

        Returns:
            Dict mapping arxiv_id to metadata (or None if not found)
        """
        results = {}
        for arxiv_id in arxiv_ids:
            results[arxiv_id] = await self.get_paper(arxiv_id)
        return results
