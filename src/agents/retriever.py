"""Retriever agent for finding popular papers in time slices."""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
import arxiv
from src.agents.types import PaperCandidate
from src.retriever.semantic_scholar import SemanticScholarRetriever
from src.config.cache import RedisCache
from src.config.logging import get_logger

logger = get_logger(__name__)


class RetrieverAgent:
    """Agent for retrieving popular papers from arXiv and conferences.

    This agent searches for papers in a specific time slice and enriches
    them with citation data from Semantic Scholar.
    """

    # Category mappings for arXiv queries
    CATEGORIES = [
        "cs.CL",  # Computation and Language (NLP)
        "cs.LG",  # Machine Learning
        "cs.AI",  # Artificial Intelligence
        "cs.CV",  # Computer Vision
    ]

    def __init__(
        self,
        s2_retriever: SemanticScholarRetriever,
        cache: RedisCache,
    ):
        """Initialize retriever agent.

        Args:
            s2_retriever: Semantic Scholar retriever for citation data
            cache: Redis cache instance
        """
        self.s2 = s2_retriever
        self.cache = cache
        self.arxiv_client = arxiv.Client()

    async def retrieve_papers(
        self,
        start_date: datetime,
        end_date: datetime,
        max_results: int = 100,
        min_citations: int = 0,
    ) -> List[PaperCandidate]:
        """Retrieve papers published within a time slice.

        Args:
            start_date: Start of time slice
            end_date: End of time slice
            max_results: Maximum number of papers to retrieve
            min_citations: Minimum citation count filter

        Returns:
            List of paper candidates with citation data
        """
        logger.info(
            "retriever_start",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            max_results=max_results
        )

        # Check cache first
        cache_key = f"{start_date.strftime('%Y%m')}"
        cached = await self._get_cached_papers(cache_key)
        if cached:
            logger.info("retriever_cache_hit", count=len(cached))
            return cached[:max_results]

        # Fetch from arXiv
        papers = await self._fetch_arxiv_papers(start_date, end_date, max_results * 2)

        # Enrich with citation data in parallel
        papers_with_citations = await self._enrich_with_citations(papers)

        # Filter by citation count
        filtered = [p for p in papers_with_citations if p.citation_count >= min_citations]

        # Sort by citation count (descending)
        sorted_papers = sorted(filtered, key=lambda p: p.citation_count, reverse=True)

        # Cache the results
        await self._cache_papers(cache_key, sorted_papers)

        logger.info("retriever_complete", count=len(sorted_papers))

        return sorted_papers[:max_results]

    async def _fetch_arxiv_papers(
        self,
        start_date: datetime,
        end_date: datetime,
        max_results: int
    ) -> List[PaperCandidate]:
        """Fetch papers from arXiv.

        Args:
            start_date: Start date
            end_date: End date
            max_results: Maximum results

        Returns:
            List of paper candidates
        """
        papers = []

        # Build query for multiple categories
        # Format: cat:cs.CL OR cat:cs.LG OR cat:cs.AI OR cat:cs.CV
        category_query = " OR ".join([f"cat:{cat}" for cat in self.CATEGORIES])

        # arXiv Search API doesn't support date range directly in query,
        # so we fetch more and filter by date
        search = arxiv.Search(
            query=category_query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )

        try:
            logger.info("arxiv_search", query=category_query, max_results=max_results)

            for result in self.arxiv_client.results(search):
                # Filter by date range
                if start_date <= result.published <= end_date:
                    paper = PaperCandidate(
                        arxiv_id=result.entry_id.split('/')[-1],
                        title=result.title,
                        authors=[author.name for author in result.authors],
                        abstract=result.summary.replace('\n', ' ').strip(),
                        published=result.published,
                        primary_category=result.primary_category,
                        pdf_url=result.pdf_url,
                        entry_url=result.entry_id,
                        source="arxiv"
                    )
                    papers.append(paper)

                # Stop if we've collected enough papers in date range
                if len(papers) >= max_results:
                    break

            logger.info("arxiv_fetch_complete", count=len(papers))

        except Exception as e:
            logger.error("arxiv_fetch_error", error=str(e))

        return papers

    async def _enrich_with_citations(
        self,
        papers: List[PaperCandidate]
    ) -> List[PaperCandidate]:
        """Enrich papers with citation data from Semantic Scholar.

        Args:
            papers: List of paper candidates

        Returns:
            Papers with citation data
        """
        if not papers:
            return []

        logger.info("enrich_citations_start", count=len(papers))

        # Fetch citations in parallel (with rate limiting)
        async def fetch_citation(paper: PaperCandidate) -> PaperCandidate:
            citation_data = await self.s2.get_paper_citations(paper.arxiv_id)
            if citation_data:
                paper.citation_count = citation_data["citation_count"]
                paper.influential_citation_count = citation_data["influential_citation_count"]
            return paper

        # Process in batches to avoid overwhelming the API
        batch_size = 10
        enriched = []

        for i in range(0, len(papers), batch_size):
            batch = papers[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[fetch_citation(p) for p in batch],
                return_exceptions=True
            )

            for result in batch_results:
                if isinstance(result, PaperCandidate):
                    enriched.append(result)
                else:
                    logger.warning("citation_fetch_failed", error=str(result))

            # Rate limiting: wait between batches
            if i + batch_size < len(papers):
                await asyncio.sleep(1.0)

        logger.info("enrich_citations_complete", count=len(enriched))

        return enriched

    async def _get_cached_papers(self, cache_key: str) -> Optional[List[PaperCandidate]]:
        """Get cached papers from Redis.

        Args:
            cache_key: Cache key

        Returns:
            List of papers or None
        """
        key = f"dra:citations:{cache_key}"
        try:
            data = await self.cache.client.get(key)
            if data:
                # Deserialize papers (simplified - would need proper serialization)
                logger.info("cache_hit", key=key)
                return None  # TODO: Implement proper serialization
        except Exception as e:
            logger.error("cache_get_error", key=key, error=str(e))

        return None

    async def _cache_papers(self, cache_key: str, papers: List[PaperCandidate]):
        """Cache papers to Redis.

        Args:
            cache_key: Cache key
            papers: Papers to cache
        """
        key = f"dra:citations:{cache_key}"
        try:
            # TODO: Implement proper serialization
            # For now, skip caching complex objects
            logger.info("cache_skip", key=key, reason="serialization_not_implemented")
        except Exception as e:
            logger.error("cache_set_error", key=key, error=str(e))
