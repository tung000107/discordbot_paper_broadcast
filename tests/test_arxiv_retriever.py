"""Tests for arXiv retriever."""
import pytest
from src.retriever.arxiv import ArxivRetriever


class TestArxivRetriever:
    """Test arXiv ID extraction and retrieval."""

    def test_extract_arxiv_ids_from_id(self):
        """Test extracting arXiv ID from plain ID."""
        ids = ArxivRetriever.extract_arxiv_ids("2401.01234")
        assert len(ids) == 1
        assert ids[0] == "2401.01234"

    def test_extract_arxiv_ids_from_url(self):
        """Test extracting arXiv ID from URL."""
        ids = ArxivRetriever.extract_arxiv_ids("https://arxiv.org/abs/2401.01234")
        assert len(ids) == 1
        assert "2401.01234" in ids[0]

    def test_extract_arxiv_ids_from_pdf_url(self):
        """Test extracting arXiv ID from PDF URL."""
        ids = ArxivRetriever.extract_arxiv_ids("https://arxiv.org/pdf/2401.01234.pdf")
        assert len(ids) == 1
        assert "2401.01234" in ids[0]

    def test_extract_arxiv_ids_with_version(self):
        """Test extracting arXiv ID with version."""
        ids = ArxivRetriever.extract_arxiv_ids("2401.01234v2")
        assert len(ids) == 1
        assert ids[0] == "2401.01234v2"

    def test_extract_multiple_ids(self):
        """Test extracting multiple arXiv IDs."""
        text = "Check out 2401.01234 and https://arxiv.org/abs/2402.56789"
        ids = ArxivRetriever.extract_arxiv_ids(text)
        assert len(ids) == 2

    def test_extract_no_ids(self):
        """Test when no arXiv IDs present."""
        ids = ArxivRetriever.extract_arxiv_ids("No arXiv papers here")
        assert len(ids) == 0

    @pytest.mark.asyncio
    async def test_get_paper_integration(self):
        """Integration test: Fetch a real arXiv paper.

        Note: This requires network access and may be slow.
        Consider mocking in CI/CD environments.
        """
        pytest.skip("Integration test - requires network and API access")

        # Example integration test (uncomment when needed):
        # from src.config.cache import RedisCache
        # cache = RedisCache("redis://localhost:6379/0")
        # await cache.connect()
        # retriever = ArxivRetriever(cache)
        # paper = await retriever.get_paper("2401.01234")
        # assert paper is not None
        # assert "title" in paper
        # assert "authors" in paper
        # await cache.disconnect()
