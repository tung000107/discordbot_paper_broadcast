"""Test script for agent system verification."""
import asyncio
from datetime import datetime, timedelta

from src.config.cache import RedisCache
from src.config.settings import settings
from src.llm.client import LLMClient
from src.llm.pipeline import SummarizationPipeline
from src.retriever.semantic_scholar import SemanticScholarRetriever

from src.agents import (
    RetrieverAgent,
    SummarizerAgent,
    TopicCategorizer,
    TopPapersCoordinator,
)


async def test_agent_initialization():
    """Test that all agents can be initialized."""
    print("Testing agent initialization...")

    # Initialize dependencies
    cache = RedisCache(redis_url=settings.redis_url)
    await cache.connect()
    llm_client = LLMClient(cache=cache)
    s2_retriever = SemanticScholarRetriever(
        cache=cache,
        api_key=settings.s2_api_key or None
    )

    # Initialize agents
    retriever_agent = RetrieverAgent(
        s2_retriever=s2_retriever,
        cache=cache,
    )
    print("✓ RetrieverAgent initialized")

    pipeline = SummarizationPipeline(
        llm_client=llm_client,
        cache=cache,
    )
    summarizer_agent = SummarizerAgent(
        pipeline=pipeline,
        max_concurrent=3,
    )
    print("✓ SummarizerAgent initialized")

    categorizer = TopicCategorizer(llm_client=llm_client)
    print("✓ TopicCategorizer initialized")

    # Initialize coordinator
    coordinator = TopPapersCoordinator(
        retriever=retriever_agent,
        summarizer=summarizer_agent,
        categorizer=categorizer,
    )
    print("✓ TopPapersCoordinator initialized")

    print("\n✅ All agents initialized successfully!")

    # Close Redis connection
    await cache.disconnect()


if __name__ == "__main__":
    asyncio.run(test_agent_initialization())
