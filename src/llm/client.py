"""OpenAI-compatible LLM client abstraction."""
import json
from typing import Any, AsyncIterator, Optional
from openai import AsyncOpenAI
from src.config.settings import settings
from src.config.cache import RedisCache
from src.config.logging import get_logger
from datetime import datetime

logger = get_logger(__name__)


class LLMClient:
    """OpenAI-compatible LLM client with cost tracking."""

    def __init__(self, cache: RedisCache):
        """Initialize LLM client.

        Args:
            cache: Redis cache for cost tracking
        """
        self.cache = cache
        self.client = AsyncOpenAI(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
        )

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict] = None,
    ) -> tuple[str, dict[str, Any]]:
        """Generate completion.

        Args:
            prompt: User prompt
            system: Optional system message
            model: Model name (defaults to settings.openai_model)
            temperature: Generation temperature (defaults to settings)
            max_tokens: Max output tokens (defaults to settings)
            response_format: Optional response format (e.g., {"type": "json_object"})

        Returns:
            Tuple of (completion_text, metadata)
        """
        model = model or settings.openai_model
        temperature = temperature if temperature is not None else settings.llm_temperature
        max_tokens = max_tokens or settings.llm_max_output_tokens

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            start_time = datetime.utcnow()

            logger.info(
                "llm_request",
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                has_response_format=response_format is not None,
            )

            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format:
                kwargs["response_format"] = response_format

            response = await self.client.chat.completions.create(**kwargs)

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            usage = response.usage

            # Track costs
            if usage:
                await self._track_usage(model, usage, duration_ms)

            content = response.choices[0].message.content

            metadata = {
                "model": model,
                "tokens_in": usage.prompt_tokens if usage else 0,
                "tokens_out": usage.completion_tokens if usage else 0,
                "duration_ms": duration_ms,
                "finish_reason": response.choices[0].finish_reason,
            }

            logger.info(
                "llm_response",
                **metadata,
            )

            return content, metadata

        except Exception as e:
            logger.error("llm_error", model=model, error=str(e))
            raise

    async def complete_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Generate JSON completion.

        Args:
            prompt: User prompt
            system: Optional system message
            model: Model name
            temperature: Generation temperature
            max_tokens: Max output tokens

        Returns:
            Tuple of (parsed_json, metadata)

        Raises:
            ValueError: If response is not valid JSON
        """
        content, metadata = await self.complete(
            prompt=prompt,
            system=system,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        try:
            parsed = json.loads(content)
            return parsed, metadata
        except json.JSONDecodeError as e:
            logger.error("llm_json_parse_error", content=content[:200], error=str(e))
            raise ValueError(f"Failed to parse JSON response: {e}")

    async def stream_complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Generate streaming completion.

        Args:
            prompt: User prompt
            system: Optional system message
            model: Model name
            temperature: Generation temperature
            max_tokens: Max output tokens

        Yields:
            Text chunks
        """
        model = model or settings.openai_model
        temperature = temperature if temperature is not None else settings.llm_temperature
        max_tokens = max_tokens or settings.llm_max_output_tokens

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            start_time = datetime.utcnow()
            total_tokens_out = 0

            logger.info("llm_stream_request", model=model)

            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    total_tokens_out += len(text.split())  # Rough approximation
                    yield text

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            logger.info(
                "llm_stream_complete",
                model=model,
                duration_ms=duration_ms,
                approx_tokens=total_tokens_out,
            )

        except Exception as e:
            logger.error("llm_stream_error", model=model, error=str(e))
            raise

    async def _track_usage(self, model: str, usage: Any, duration_ms: float) -> None:
        """Track token usage and estimated cost.

        Args:
            model: Model name
            usage: Usage object from API
            duration_ms: Request duration
        """
        date = datetime.utcnow().strftime("%Y-%m-%d")

        # Simplified cost estimation (adjust based on actual pricing)
        # GPT-4o-mini: ~$0.15/1M input, ~$0.60/1M output
        cost_per_1k_in = 0.00015
        cost_per_1k_out = 0.0006

        if "gpt-4" in model.lower() and "mini" not in model.lower():
            cost_per_1k_in = 0.03  # GPT-4 pricing
            cost_per_1k_out = 0.06

        cost = (usage.prompt_tokens / 1000 * cost_per_1k_in +
                usage.completion_tokens / 1000 * cost_per_1k_out)

        await self.cache.increment_cost(date, "tokens_in", usage.prompt_tokens)
        await self.cache.increment_cost(date, "tokens_out", usage.completion_tokens)
        await self.cache.increment_cost(date, "cost_estimated", cost)

        logger.debug(
            "cost_tracked",
            date=date,
            tokens_in=usage.prompt_tokens,
            tokens_out=usage.completion_tokens,
            cost=cost,
        )
