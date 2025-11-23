"""Redis cache layer for Discord Research Assistant."""
import json
from typing import Any, Optional
from datetime import timedelta
import redis.asyncio as redis
from src.config.logging import get_logger

logger = get_logger(__name__)


class RedisCache:
    """Redis cache client with DRA key namespace."""

    NAMESPACE = "dra"

    # TTL constants
    TTL_METADATA = timedelta(days=7)
    TTL_SUMMARY = timedelta(days=30)
    TTL_PDF = timedelta(days=30)
    TTL_CITATIONS = timedelta(days=7)
    TTL_RATE_LIMIT = timedelta(seconds=60)

    def __init__(self, redis_url: str):
        """Initialize Redis client.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Establish Redis connection."""
        self._client = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("redis_connected", url=self.redis_url)

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            logger.info("redis_disconnected")

    @property
    def client(self) -> redis.Redis:
        """Get Redis client instance."""
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client

    def _key(self, *parts: str) -> str:
        """Build namespaced key.

        Args:
            *parts: Key components

        Returns:
            Formatted key with namespace
        """
        return f"{self.NAMESPACE}:{':'.join(parts)}"

    # Paper metadata cache
    async def get_paper_metadata(self, arxiv_id: str) -> Optional[dict[str, Any]]:
        """Get cached paper metadata.

        Args:
            arxiv_id: arXiv paper ID

        Returns:
            Paper metadata dict or None
        """
        key = self._key("paper", arxiv_id, "meta")
        data = await self.client.get(key)
        if data:
            logger.debug("cache_hit", key=key, type="metadata")
            return json.loads(data)
        logger.debug("cache_miss", key=key, type="metadata")
        return None

    async def set_paper_metadata(self, arxiv_id: str, metadata: dict[str, Any]) -> None:
        """Cache paper metadata.

        Args:
            arxiv_id: arXiv paper ID
            metadata: Paper metadata dict
        """
        key = self._key("paper", arxiv_id, "meta")
        await self.client.setex(
            key,
            self.TTL_METADATA,
            json.dumps(metadata, ensure_ascii=False)
        )
        logger.debug("cache_set", key=key, type="metadata", ttl=self.TTL_METADATA.total_seconds())

    # Summary cache
    async def get_summary(self, arxiv_id: str, model: str, version: str = "v1") -> Optional[dict[str, Any]]:
        """Get cached summary.

        Args:
            arxiv_id: arXiv paper ID
            model: Model name used
            version: Summary version

        Returns:
            Summary dict or None
        """
        key = self._key("paper", arxiv_id, "summary", model, version)
        data = await self.client.get(key)
        if data:
            logger.debug("cache_hit", key=key, type="summary")
            return json.loads(data)
        logger.debug("cache_miss", key=key, type="summary")
        return None

    async def set_summary(self, arxiv_id: str, model: str, summary: dict[str, Any], version: str = "v1") -> None:
        """Cache summary.

        Args:
            arxiv_id: arXiv paper ID
            model: Model name used
            summary: Summary dict
            version: Summary version
        """
        key = self._key("paper", arxiv_id, "summary", model, version)
        await self.client.setex(
            key,
            self.TTL_SUMMARY,
            json.dumps(summary, ensure_ascii=False)
        )
        logger.debug("cache_set", key=key, type="summary", ttl=self.TTL_SUMMARY.total_seconds())

    # PDF cache
    async def get_pdf_info(self, arxiv_id: str, model: str, version: str = "v1") -> Optional[dict[str, Any]]:
        """Get cached PDF info.

        Args:
            arxiv_id: arXiv paper ID
            model: Model name used
            version: PDF version

        Returns:
            PDF info dict or None
        """
        key = self._key("pdf", arxiv_id, model, version)
        data = await self.client.get(key)
        if data:
            logger.debug("cache_hit", key=key, type="pdf")
            return json.loads(data)
        logger.debug("cache_miss", key=key, type="pdf")
        return None

    async def set_pdf_info(self, arxiv_id: str, model: str, pdf_info: dict[str, Any], version: str = "v1") -> None:
        """Cache PDF info.

        Args:
            arxiv_id: arXiv paper ID
            model: Model name used
            pdf_info: PDF info dict (path, hash, size)
            version: PDF version
        """
        key = self._key("pdf", arxiv_id, model, version)
        await self.client.setex(
            key,
            self.TTL_PDF,
            json.dumps(pdf_info, ensure_ascii=False)
        )
        logger.debug("cache_set", key=key, type="pdf", ttl=self.TTL_PDF.total_seconds())

    # Citations cache
    async def get_citations(self, month: str) -> Optional[dict[str, Any]]:
        """Get cached citations for a month.

        Args:
            month: Month in ISO format (YYYY-MM)

        Returns:
            Citations dict or None
        """
        key = self._key("citations", month)
        data = await self.client.get(key)
        if data:
            logger.debug("cache_hit", key=key, type="citations")
            return json.loads(data)
        logger.debug("cache_miss", key=key, type="citations")
        return None

    async def set_citations(self, month: str, citations: dict[str, Any]) -> None:
        """Cache citations for a month.

        Args:
            month: Month in ISO format (YYYY-MM)
            citations: Citations dict
        """
        key = self._key("citations", month)
        await self.client.setex(
            key,
            self.TTL_CITATIONS,
            json.dumps(citations, ensure_ascii=False)
        )
        logger.debug("cache_set", key=key, type="citations", ttl=self.TTL_CITATIONS.total_seconds())

    # Cost tracking
    async def increment_cost(self, date: str, field: str, value: float) -> None:
        """Increment daily cost metric.

        Args:
            date: Date in ISO format (YYYY-MM-DD)
            field: Metric field name (tokens_in, tokens_out, cost_estimated)
            value: Value to increment
        """
        key = self._key("cost", "daily", date)
        await self.client.hincrbyfloat(key, field, value)
        await self.client.expire(key, timedelta(days=90))

    async def get_daily_cost(self, date: str) -> dict[str, float]:
        """Get daily cost metrics.

        Args:
            date: Date in ISO format (YYYY-MM-DD)

        Returns:
            Dict of cost metrics
        """
        key = self._key("cost", "daily", date)
        data = await self.client.hgetall(key)
        return {k: float(v) for k, v in data.items()}

    # Rate limiting
    async def check_rate_limit(self, user_id: str, per_min: int, per_day: int) -> tuple[bool, str]:
        """Check if user is within rate limits.

        Args:
            user_id: Discord user ID
            per_min: Requests allowed per minute
            per_day: Requests allowed per day

        Returns:
            Tuple of (allowed, reason)
        """
        import time
        from datetime import datetime

        now = int(time.time())
        minute_key = self._key("rate", "discord", user_id, "min", str(now // 60))
        day_key = self._key("rate", "discord", user_id, "day", datetime.utcnow().strftime("%Y-%m-%d"))

        # Check minute limit
        minute_count = await self.client.incr(minute_key)
        await self.client.expire(minute_key, 60)

        if minute_count > per_min:
            return False, f"Rate limit: {per_min} requests per minute"

        # Check day limit
        day_count = await self.client.incr(day_key)
        await self.client.expire(day_key, 86400)

        if day_count > per_day:
            return False, f"Rate limit: {per_day} requests per day"

        return True, ""
