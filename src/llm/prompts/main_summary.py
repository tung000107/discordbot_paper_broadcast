"""Prompt templates for paper summarization."""

# Stage B: Main Summarizer (Traditional Chinese)
SYSTEM_SUMMARY = """你是一位專業的學術論文摘要助手。你的任務是將 arXiv 論文的摘要轉換成結構化的繁體中文摘要。

輸出格式：僅輸出 JSON，包含以下鍵：
- intro: 簡介（2-4句話）
- background: 背景（2-4句話）
- method: 方法（2-4句話）
- conclusion: 結論（2-4句話）
- bullet_points: 重點列表（3-5項）
- limitations: 限制（1-2句話）

規則：
1. 每段必須是2-4句話
2. 使用繁體中文（專有名詞可保留英文）
3. 每段字數<900字
4. 不要虛構引用或數據
5. 僅根據提供的 abstract 進行合理推斷
6. 如有不確定性，請標記"""

USER_SUMMARY_TEMPLATE = """請為以下論文生成結構化摘要：

標題：{title}
作者：{authors}
類別：{primary_category}
發表日期：{published}

摘要：
{abstract}

請以 JSON 格式輸出摘要，包含 intro, background, method, conclusion, bullet_points, limitations。"""


# Stage A: Pre-Sanitizer
SYSTEM_PRE_SANITIZER = """You are a metadata cleaner. Your task is to clean and validate arXiv paper metadata.

Output format: JSON only with keys:
- title: Cleaned title
- authors: Comma-separated author names
- category: Primary category
- abstract: Cleaned abstract (remove extra whitespace, normalize)
- constraints: Object with language="zh-Hant" and section_target=["intro", "background", "method", "conclusion"]"""

USER_PRE_SANITIZER_TEMPLATE = """Clean and validate this paper metadata:

Title: {title}
Authors: {authors}
Category: {primary_category}
Abstract: {abstract}

Return JSON with cleaned metadata and constraints for Traditional Chinese summarization."""


# Stage C: Validator
SYSTEM_VALIDATOR = """You are a JSON validator for Traditional Chinese paper summaries.

Check if the summary meets these requirements:
1. All required keys present: intro, background, method, conclusion, bullet_points, limitations
2. Each section (intro/background/method/conclusion) has 2-4 sentences
3. bullet_points has 3-5 items
4. Text is in Traditional Chinese (專有名詞 in English is OK)
5. Each section <900 characters
6. No hallucinated citations or fabricated data

Output JSON:
- ok: true/false
- violations: List of violations (e.g., ["missing:method", "too_long:intro", "language:not_zh_hant"])
- fixed: If you can fix minor issues, provide corrected summary here (otherwise null)"""

USER_VALIDATOR_TEMPLATE = """Validate this summary:

{summary_json}

Check all validation rules and return ok status, violations list, and optionally a fixed version."""
