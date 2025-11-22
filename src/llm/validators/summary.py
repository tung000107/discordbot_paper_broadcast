"""Validators for summary JSON outputs."""
import re
from typing import Any


class SummaryValidator:
    """Validator for TDS §4.3 Stage B summary contract."""

    REQUIRED_KEYS = ["intro", "background", "method", "conclusion", "bullet_points", "limitations"]
    SECTION_KEYS = ["intro", "background", "method", "conclusion"]

    MAX_CHARS_PER_SECTION = 900
    MIN_SENTENCES = 2
    MAX_SENTENCES = 4
    MIN_BULLET_POINTS = 3
    MAX_BULLET_POINTS = 5

    @staticmethod
    def count_sentences(text: str) -> int:
        """Count sentences in text.

        Args:
            text: Input text

        Returns:
            Number of sentences
        """
        # Simple sentence counter (split by period, exclamation, question mark)
        sentences = re.split(r'[。!?！？.]+', text)
        return len([s for s in sentences if s.strip()])

    @classmethod
    def validate(cls, summary: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate summary JSON.

        Args:
            summary: Summary dict from Stage B

        Returns:
            Tuple of (is_valid, violations)
        """
        violations = []

        # Check required keys
        for key in cls.REQUIRED_KEYS:
            if key not in summary:
                violations.append(f"missing:{key}")

        if violations:
            return False, violations

        # Check section sentence counts and length
        for section in cls.SECTION_KEYS:
            text = summary[section]

            # Check character limit
            if len(text) > cls.MAX_CHARS_PER_SECTION:
                violations.append(f"too_long:{section}")

            # Check sentence count
            sentence_count = cls.count_sentences(text)
            if sentence_count < cls.MIN_SENTENCES:
                violations.append(f"too_few_sentences:{section}")
            elif sentence_count > cls.MAX_SENTENCES:
                violations.append(f"too_many_sentences:{section}")

        # Check bullet points
        bullet_points = summary.get("bullet_points", [])
        if not isinstance(bullet_points, list):
            violations.append("invalid_type:bullet_points")
        elif len(bullet_points) < cls.MIN_BULLET_POINTS:
            violations.append("too_few:bullet_points")
        elif len(bullet_points) > cls.MAX_BULLET_POINTS:
            violations.append("too_many:bullet_points")

        # Check Traditional Chinese (basic check for Chinese characters)
        for section in cls.SECTION_KEYS + ["limitations"]:
            text = summary.get(section, "")
            # Check if text contains Chinese characters
            if text and not re.search(r'[\u4e00-\u9fff]', text):
                violations.append(f"language:not_chinese:{section}")

        return len(violations) == 0, violations

    @classmethod
    def truncate_sections(cls, summary: dict[str, Any]) -> dict[str, Any]:
        """Truncate sections that exceed limits.

        Args:
            summary: Summary dict

        Returns:
            Truncated summary
        """
        result = summary.copy()

        for section in cls.SECTION_KEYS:
            if section in result:
                text = result[section]
                if len(text) > cls.MAX_CHARS_PER_SECTION:
                    # Truncate to max chars, try to end at sentence boundary
                    truncated = text[:cls.MAX_CHARS_PER_SECTION]
                    # Find last sentence ending
                    for delimiter in ['。', '！', '？', '.', '!', '?']:
                        last_idx = truncated.rfind(delimiter)
                        if last_idx > 0:
                            truncated = truncated[:last_idx + 1]
                            break
                    result[section] = truncated

        # Truncate bullet points
        if "bullet_points" in result:
            result["bullet_points"] = result["bullet_points"][:cls.MAX_BULLET_POINTS]

        return result
