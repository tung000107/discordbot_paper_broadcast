"""Multi-stage LLM pipeline for paper summarization."""
import json
from typing import Any, AsyncIterator, Optional
from src.llm.client import LLMClient
from src.llm.prompts.main_summary import (
    SYSTEM_PRE_SANITIZER,
    USER_PRE_SANITIZER_TEMPLATE,
    SYSTEM_SUMMARY,
    USER_SUMMARY_TEMPLATE,
    SYSTEM_VALIDATOR,
    USER_VALIDATOR_TEMPLATE,
)
from src.llm.validators.summary import SummaryValidator
from src.config.settings import settings
from src.config.cache import RedisCache
from src.config.logging import get_logger

logger = get_logger(__name__)


class SummarizationPipeline:
    """Multi-stage LLM pipeline implementing TDS §4.3."""

    def __init__(self, llm_client: LLMClient, cache: RedisCache):
        """Initialize pipeline.

        Args:
            llm_client: LLM client instance
            cache: Redis cache instance
        """
        self.llm = llm_client
        self.cache = cache
        self.validator = SummaryValidator()

    async def summarize(self, paper_metadata: dict[str, Any]) -> dict[str, Any]:
        """Run complete summarization pipeline.

        Args:
            paper_metadata: Paper metadata from arXiv retriever

        Returns:
            Final validated summary dict

        Raises:
            ValueError: If pipeline fails after retries
        """
        arxiv_id = paper_metadata["arxiv_id"].split('v')[0]  # Normalize ID

        # Check cache first
        cached_summary = await self.cache.get_summary(
            arxiv_id,
            settings.openai_model,
            version="v1"
        )
        if cached_summary:
            logger.info("summary_cache_hit", arxiv_id=arxiv_id)
            return cached_summary

        logger.info("summary_pipeline_start", arxiv_id=arxiv_id)

        # Stage A: Pre-sanitizer (optional, using small model)
        cleaned_metadata = await self._stage_a_sanitize(paper_metadata)

        # Stage B: Main summarizer
        summary = await self._stage_b_summarize(cleaned_metadata)

        # Stage C: Validator with retry
        final_summary = await self._stage_c_validate(summary, retry=True)

        # Cache the result
        await self.cache.set_summary(
            arxiv_id,
            settings.openai_model,
            final_summary,
            version="v1"
        )

        logger.info("summary_pipeline_complete", arxiv_id=arxiv_id)

        return final_summary

    async def _stage_a_sanitize(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Stage A: Pre-sanitize metadata with small model.

        Args:
            metadata: Raw paper metadata

        Returns:
            Cleaned metadata
        """
        logger.info("stage_a_start")

        prompt = USER_PRE_SANITIZER_TEMPLATE.format(
            title=metadata["title"],
            authors=", ".join(metadata["authors"]),
            primary_category=metadata["primary_category"],
            abstract=metadata["abstract"],
        )

        try:
            cleaned, _ = await self.llm.complete_json(
                prompt=prompt,
                system=SYSTEM_PRE_SANITIZER,
                model=settings.openai_model_pre,
                temperature=0.1,
            )
            logger.info("stage_a_complete")
            return cleaned
        except Exception as e:
            logger.warning("stage_a_failed", error=str(e), fallback=True)
            # Fallback: return original metadata
            return {
                "title": metadata["title"],
                "authors": ", ".join(metadata["authors"]),
                "category": metadata["primary_category"],
                "abstract": metadata["abstract"],
                "constraints": {
                    "language": "zh-Hant",
                    "section_target": ["intro", "background", "method", "conclusion"]
                }
            }

    async def _stage_b_summarize(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Stage B: Generate main summary.

        Args:
            metadata: Cleaned metadata from Stage A

        Returns:
            Summary dict

        Raises:
            ValueError: If summary generation fails
        """
        logger.info("stage_b_start")

        prompt = USER_SUMMARY_TEMPLATE.format(
            title=metadata.get("title", ""),
            authors=metadata.get("authors", ""),
            primary_category=metadata.get("category", ""),
            published=metadata.get("published", ""),
            abstract=metadata.get("abstract", ""),
        )

        summary, meta = await self.llm.complete_json(
            prompt=prompt,
            system=SYSTEM_SUMMARY,
            model=settings.openai_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_output_tokens,
        )

        logger.info("stage_b_complete", tokens=meta["tokens_out"])

        return summary

    async def _stage_c_validate(
        self,
        summary: dict[str, Any],
        retry: bool = True
    ) -> dict[str, Any]:
        """Stage C: Validate and optionally fix summary.

        Args:
            summary: Summary from Stage B
            retry: Whether to retry with corrections on validation failure

        Returns:
            Validated (and possibly corrected) summary

        Raises:
            ValueError: If validation fails after retry
        """
        logger.info("stage_c_start")

        # Local validation first
        is_valid, violations = self.validator.validate(summary)

        if is_valid:
            logger.info("stage_c_valid_local")
            return summary

        logger.warning("stage_c_violations", violations=violations)

        # Try LLM-based validation/fixing
        prompt = USER_VALIDATOR_TEMPLATE.format(
            summary_json=json.dumps(summary, ensure_ascii=False, indent=2)
        )

        try:
            validation_result, _ = await self.llm.complete_json(
                prompt=prompt,
                system=SYSTEM_VALIDATOR,
                model=settings.openai_model_val,
                temperature=0.0,  # Low temperature for validation
            )

            if validation_result.get("ok"):
                logger.info("stage_c_validator_ok")
                return validation_result.get("fixed") or summary

            # If validator provides a fix, use it
            if validation_result.get("fixed"):
                fixed = validation_result["fixed"]
                # Re-validate the fixed version
                is_valid, _ = self.validator.validate(fixed)
                if is_valid:
                    logger.info("stage_c_fixed")
                    return fixed

        except Exception as e:
            logger.error("stage_c_validator_error", error=str(e))

        # Fallback: truncate sections to meet basic requirements
        logger.warning("stage_c_fallback_truncate")
        return self.validator.truncate_sections(summary)

    async def stream_summarize(
        self,
        paper_metadata: dict[str, Any]
    ) -> AsyncIterator[tuple[str, str, dict[str, Any]]]:
        """Stream summary generation with section markers.

        This is a simplified streaming version that yields sections as they complete.
        For full streaming, we'd need streaming support in Stage B.

        Args:
            paper_metadata: Paper metadata

        Yields:
            Tuples of (section, partial_text, metadata)
        """
        arxiv_id = paper_metadata["arxiv_id"].split('v')[0]

        logger.info("stream_pipeline_start", arxiv_id=arxiv_id)

        # Run full pipeline (non-streaming for now)
        summary = await self.summarize(paper_metadata)

        # Yield sections one by one
        sections = ["intro", "background", "method", "conclusion"]
        for idx, section in enumerate(sections):
            if section in summary:
                yield section, summary[section], {
                    "progress": (idx + 1) / len(sections),
                    "section": section,
                }

        logger.info("stream_pipeline_complete", arxiv_id=arxiv_id)
