"""Test retriever agent to debug why no papers are found."""
import asyncio
from datetime import datetime
from src.config.cache import RedisCache
from src.config.settings import settings
from src.retriever.semantic_scholar import SemanticScholarRetriever
from src.agents.retriever import RetrieverAgent


async def test_retriever():
    """Test the retriever agent."""
    print("Testing RetrieverAgent to find issues...\n")

    # Initialize dependencies
    cache = RedisCache(redis_url=settings.redis_url)
    await cache.connect()

    s2_retriever = SemanticScholarRetriever(
        cache=cache,
        api_key=settings.s2_api_key or None
    )

    retriever = RetrieverAgent(
        s2_retriever=s2_retriever,
        cache=cache,
    )

    # Test with current month (use timezone-aware datetimes)
    from datetime import timezone
    now = datetime.now(timezone.utc)
    start_date = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    end_date = now

    print(f"Testing retrieval for date range:")
    print(f"  Start: {start_date}")
    print(f"  End: {end_date}")
    print(f"  Start timezone: {start_date.tzinfo}")
    print(f"  End timezone: {end_date.tzinfo}")
    print()

    # Try to retrieve papers
    print("Fetching papers from arXiv...")
    papers = await retriever.retrieve_papers(
        start_date=start_date,
        end_date=end_date,
        max_results=10,
        min_citations=0,  # Set to 0 to see if we get any papers at all
    )

    print(f"\n✓ Retrieved {len(papers)} papers")

    if papers:
        print("\nFirst 3 papers:")
        for i, paper in enumerate(papers[:3], 1):
            print(f"\n{i}. {paper.title[:80]}")
            print(f"   arXiv ID: {paper.arxiv_id}")
            print(f"   Published: {paper.published} (tzinfo: {paper.published.tzinfo})")
            print(f"   Citations: {paper.citation_count}")
            print(f"   Category: {paper.primary_category}")
    else:
        print("\n⚠️  No papers found!")
        print("\nLet's try fetching directly from arXiv to debug...")

        # Debug: Try direct arXiv fetch
        import arxiv
        client = arxiv.Client()
        search = arxiv.Search(
            query="cat:cs.CL OR cat:cs.LG",
            max_results=5,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )

        print("\nDirect arXiv API test (first 5 results):")
        for result in client.results(search):
            print(f"\n  Title: {result.title[:60]}")
            print(f"  Published: {result.published}")
            print(f"  Timezone: {result.published.tzinfo}")
            print(f"  In range? {start_date <= result.published <= end_date}")
            print(f"  Comparison: {start_date} <= {result.published} <= {end_date}")

    await cache.disconnect()
    print("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(test_retriever())
