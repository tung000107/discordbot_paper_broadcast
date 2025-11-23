"""Coordinator for orchestrating retriever and summarizer agents."""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict
from collections import defaultdict

from src.agents.types import PaperCandidate, RankedPaper, TopicCategory
from src.agents.retriever import RetrieverAgent
from src.agents.summarizer import SummarizerAgent
from src.agents.categorizer import TopicCategorizer
from src.config.logging import get_logger

logger = get_logger(__name__)


class TopPapersCoordinator:
    """Coordinates retrieval, categorization, and summarization of top papers.

    This coordinator implements a two-agent pipeline:
    1. Retriever agent finds popular papers in a time slice
    2. Summarizer agent generates summaries in parallel

    Both agents work concurrently with the categorizer to produce
    ranked papers organized by topic.
    """

    def __init__(
        self,
        retriever: RetrieverAgent,
        summarizer: SummarizerAgent,
        categorizer: TopicCategorizer,
    ):
        """Initialize coordinator.

        Args:
            retriever: Retriever agent
            summarizer: Summarizer agent
            categorizer: Topic categorizer
        """
        self.retriever = retriever
        self.summarizer = summarizer
        self.categorizer = categorizer

    async def get_top_papers(
        self,
        month: str,
        topic_filter: Optional[TopicCategory] = None,
        top_n: int = 20,
        min_citations: Optional[int] = None,
    ) -> Dict[TopicCategory, List[RankedPaper]]:
        """Get top papers for a month, organized by topic.

        This method orchestrates the entire pipeline:
        1. Parse month and compute time range
        2. Retrieve papers (agent 1)
        3. Categorize and summarize papers in parallel (agent 2 + categorizer)
        4. Rank papers by score
        5. Group by topic

        Args:
            month: Month in YYYY-MM format
            topic_filter: Optional topic filter
            top_n: Number of top papers to return
            min_citations: Minimum citation count

        Returns:
            Dict mapping topics to ranked papers
        """
        logger.info(
            "coordinator_start",
            month=month,
            topic_filter=topic_filter.value if topic_filter else None,
            top_n=top_n
        )

        # Parse month to date range
        start_date, end_date = self._parse_month(month)

        # Adaptive minimum citations based on paper age
        if min_citations is None:
            now_utc = datetime.now(timezone.utc)
            months_old = (now_utc.year - start_date.year) * 12 + (now_utc.month - start_date.month)

            if months_old == 0:  # Current month
                min_citations = 0
            elif months_old == 1:  # Last month
                min_citations = 1
            elif months_old <= 3:  # Last 3 months
                min_citations = 2
            elif months_old <= 6:  # Last 6 months
                min_citations = 3
            else:  # Older papers
                min_citations = 5

            logger.info(
                "adaptive_min_citations",
                month=month,
                months_old=months_old,
                min_citations=min_citations
            )

        # Step 1: Retrieve papers (Agent 1)
        logger.info("step_1_retrieve", start_date=start_date.isoformat(), end_date=end_date.isoformat())
        papers = await self.retriever.retrieve_papers(
            start_date=start_date,
            end_date=end_date,
            max_results=top_n * 3,  # Retrieve more to ensure we have enough after filtering
            min_citations=min_citations,
        )

        if not papers:
            logger.warning("no_papers_found")
            return {}

        # Step 2: Categorize and summarize in parallel
        logger.info("step_2_parallel_processing", count=len(papers))

        # Run categorization and summarization concurrently
        categorization_task = self._categorize_papers(papers)
        summarization_task = self.summarizer.summarize_papers(papers)

        categories, summaries = await asyncio.gather(
            categorization_task,
            summarization_task
        )

        # Step 3: Build ranked papers
        logger.info("step_3_rank")
        ranked_papers = []
        for paper in papers:
            topic = categories.get(paper.arxiv_id, TopicCategory.OTHER)
            summary = summaries.get(paper.arxiv_id)

            # Apply topic filter if specified
            if topic_filter and topic != topic_filter:
                continue

            # Calculate ranking score
            score = self._calculate_score(paper)

            ranked = RankedPaper(
                candidate=paper,
                score=score,
                topic=topic,
                summary=summary,
            )
            ranked_papers.append(ranked)

        # Sort by score (descending)
        ranked_papers.sort(key=lambda p: p.score, reverse=True)

        # Step 4: Group by topic
        logger.info("step_4_group_by_topic")
        grouped = self._group_by_topic(ranked_papers[:top_n])

        logger.info(
            "coordinator_complete",
            total_papers=len(ranked_papers),
            topics=list(grouped.keys())
        )

        return grouped

    async def _categorize_papers(
        self,
        papers: List[PaperCandidate]
    ) -> Dict[str, TopicCategory]:
        """Categorize papers in parallel.

        Args:
            papers: List of papers

        Returns:
            Dict mapping arxiv_id to topic
        """
        logger.info("categorize_start", count=len(papers))

        tasks = [self.categorizer.categorize(paper) for paper in papers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        categories = {}
        for paper, result in zip(papers, results):
            if isinstance(result, TopicCategory):
                categories[paper.arxiv_id] = result
            else:
                categories[paper.arxiv_id] = TopicCategory.OTHER
                logger.warning(
                    "categorize_failed",
                    arxiv_id=paper.arxiv_id,
                    error=str(result) if isinstance(result, Exception) else "unknown"
                )

        logger.info("categorize_complete", count=len(categories))
        return categories

    def _calculate_score(self, paper: PaperCandidate) -> float:
        """Calculate ranking score for a paper.

        Score formula (per TDS monthly push ranking):
        - Citation count: 70% weight
        - Recency: 20% weight
        - Influential citations: 10% weight

        Args:
            paper: Paper candidate

        Returns:
            Score (higher is better)
        """
        # Citation score (normalized by log scale to avoid extreme values)
        import math
        citation_score = math.log(paper.citation_count + 1)

        # Recency score (papers from last 30 days get boost)
        now_utc = datetime.now(timezone.utc)
        days_old = (now_utc - paper.published).days
        recency_score = max(0, 1 - (days_old / 365))  # Decay over 1 year

        # Influential citation score
        influential_score = math.log(paper.influential_citation_count + 1)

        # Weighted combination
        score = (
            citation_score * 0.7 +
            recency_score * 0.2 +
            influential_score * 0.1
        )

        return score

    def _group_by_topic(
        self,
        papers: List[RankedPaper]
    ) -> Dict[TopicCategory, List[RankedPaper]]:
        """Group papers by topic.

        Args:
            papers: List of ranked papers

        Returns:
            Dict mapping topics to papers
        """
        grouped = defaultdict(list)
        for paper in papers:
            grouped[paper.topic].append(paper)

        # Sort papers within each topic by score
        for topic in grouped:
            grouped[topic].sort(key=lambda p: p.score, reverse=True)

        return dict(grouped)

    def _parse_month(self, month: str) -> tuple[datetime, datetime]:
        """Parse month string to date range.

        Args:
            month: Month in YYYY-MM format

        Returns:
            Tuple of (start_date, end_date)
        """
        try:
            year, month_num = map(int, month.split('-'))
            # Create timezone-aware datetimes (UTC) to match arXiv API
            start_date = datetime(year, month_num, 1, tzinfo=timezone.utc)

            # Calculate end date (last day of month)
            if month_num == 12:
                end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
            else:
                end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc) - timedelta(days=1)

            # Set time to end of day
            end_date = end_date.replace(hour=23, minute=59, second=59)

            return start_date, end_date

        except Exception as e:
            logger.error("month_parse_error", month=month, error=str(e))
            # Fallback: return current month (UTC)
            now = datetime.now(timezone.utc)
            start_date = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            if now.month == 12:
                end_date = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
            else:
                end_date = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
            end_date = end_date.replace(hour=23, minute=59, second=59)
            return start_date, end_date
