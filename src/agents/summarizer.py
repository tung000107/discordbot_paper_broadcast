"""Summarizer agent for parallel paper summarization."""
import asyncio
from typing import List, Optional
from src.agents.types import PaperCandidate
from src.llm.pipeline import SummarizationPipeline
from src.config.logging import get_logger

logger = get_logger(__name__)


class SummarizerAgent:
    """Agent for summarizing papers in parallel.

    This agent uses the LLM pipeline to generate Traditional Chinese
    summaries for multiple papers concurrently.
    """

    def __init__(
        self,
        pipeline: SummarizationPipeline,
        max_concurrent: int = 3,
    ):
        """Initialize summarizer agent.

        Args:
            pipeline: LLM summarization pipeline
            max_concurrent: Maximum concurrent summarization tasks
        """
        self.pipeline = pipeline
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def summarize_papers(
        self,
        papers: List[PaperCandidate],
    ) -> dict[str, Optional[dict]]:
        """Summarize multiple papers in parallel.

        Args:
            papers: List of paper candidates to summarize

        Returns:
            Dict mapping arxiv_id to summary dict (or None if failed)
        """
        logger.info("summarizer_start", count=len(papers), max_concurrent=self.max_concurrent)

        # Create tasks for parallel execution
        tasks = [self._summarize_with_semaphore(paper) for paper in papers]

        # Execute in parallel with semaphore limiting concurrency
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dictionary
        summaries = {}
        for paper, result in zip(papers, results):
            if isinstance(result, dict):
                summaries[paper.arxiv_id] = result
                logger.info("summarize_success", arxiv_id=paper.arxiv_id)
            else:
                summaries[paper.arxiv_id] = None
                logger.error(
                    "summarize_failed",
                    arxiv_id=paper.arxiv_id,
                    error=str(result) if isinstance(result, Exception) else "unknown"
                )

        success_count = sum(1 for s in summaries.values() if s is not None)
        logger.info("summarizer_complete", total=len(papers), success=success_count)

        return summaries

    async def _summarize_with_semaphore(self, paper: PaperCandidate) -> dict:
        """Summarize a single paper with semaphore control.

        Args:
            paper: Paper candidate

        Returns:
            Summary dict

        Raises:
            Exception: If summarization fails
        """
        async with self.semaphore:
            logger.info("summarize_start", arxiv_id=paper.arxiv_id, title=paper.title[:50])

            # Convert PaperCandidate to metadata format expected by pipeline
            metadata = {
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "authors": paper.authors,
                "abstract": paper.abstract,
                "published": paper.published.isoformat(),
                "primary_category": paper.primary_category,
                "pdf_url": paper.pdf_url,
                "entry_url": paper.entry_url,
            }

            # Run through LLM pipeline
            summary = await self.pipeline.summarize(metadata)

            return summary

    async def summarize_single(self, paper: PaperCandidate) -> Optional[dict]:
        """Summarize a single paper (convenience method).

        Args:
            paper: Paper candidate

        Returns:
            Summary dict or None if failed
        """
        try:
            return await self._summarize_with_semaphore(paper)
        except Exception as e:
            logger.error("summarize_single_error", arxiv_id=paper.arxiv_id, error=str(e))
            return None
