"""Topic categorization using LLM."""
import json
from typing import Optional
from src.llm.client import LLMClient
from src.agents.types import TopicCategory, PaperCandidate
from src.config.logging import get_logger

logger = get_logger(__name__)

SYSTEM_CATEGORIZER = """你是一個專業的論文主題分類專家。根據論文的標題、摘要和類別，將論文分類到以下主題之一：

**主題定義**：
- **LLM架構**: 大型語言模型的架構創新、訓練方法、模型優化
- **LLM應用**: 使用LLM解決實際問題的應用研究
- **RAG改良**: 檢索增強生成(RAG)的技術改進、架構優化
- **RAG應用**: RAG技術的實際應用案例
- **OCR**: 光學字符識別相關技術
- **LLM Router**: 模型路由、多模型協作系統
- **其他**: 不屬於以上任何類別

請以JSON格式返回分類結果，包含主題和信心分數(0-1)。

範例輸出：
```json
{
  "topic": "LLM架構",
  "confidence": 0.95,
  "reasoning": "論文提出新的transformer架構變體"
}
```
"""

USER_CATEGORIZER_TEMPLATE = """論文資訊：

標題: {title}
類別: {category}
摘要: {abstract}

請分類此論文的主題。"""


class TopicCategorizer:
    """Categorizes papers into topic categories using LLM."""

    def __init__(self, llm_client: LLMClient):
        """Initialize categorizer.

        Args:
            llm_client: LLM client instance
        """
        self.llm = llm_client

    async def categorize(self, paper: PaperCandidate) -> TopicCategory:
        """Categorize a paper into a topic.

        Args:
            paper: Paper candidate to categorize

        Returns:
            TopicCategory enum value
        """
        prompt = USER_CATEGORIZER_TEMPLATE.format(
            title=paper.title,
            category=paper.primary_category,
            abstract=paper.abstract[:500],  # Limit abstract length
        )

        try:
            result, meta = await self.llm.complete_json(
                prompt=prompt,
                system=SYSTEM_CATEGORIZER,
                model=None,  # Use default model
                temperature=0.0,  # Deterministic categorization
            )

            topic_str = result.get("topic", "其他")
            confidence = result.get("confidence", 0.0)

            logger.info(
                "categorize_complete",
                arxiv_id=paper.arxiv_id,
                topic=topic_str,
                confidence=confidence
            )

            # Map topic string to enum
            topic_map = {
                "LLM架構": TopicCategory.LLM_ARCHITECTURE,
                "LLM應用": TopicCategory.LLM_APPLICATION,
                "RAG改良": TopicCategory.RAG_IMPROVEMENT,
                "RAG應用": TopicCategory.RAG_APPLICATION,
                "OCR": TopicCategory.OCR,
                "LLM Router": TopicCategory.LLM_ROUTER,
                "其他": TopicCategory.OTHER,
            }

            return topic_map.get(topic_str, TopicCategory.OTHER)

        except Exception as e:
            logger.error("categorize_error", arxiv_id=paper.arxiv_id, error=str(e))
            # Fallback: use primary category heuristics
            return self._heuristic_categorize(paper)

    def _heuristic_categorize(self, paper: PaperCandidate) -> TopicCategory:
        """Fallback heuristic categorization based on keywords.

        Args:
            paper: Paper candidate

        Returns:
            TopicCategory enum value
        """
        text = f"{paper.title} {paper.abstract}".lower()

        if any(kw in text for kw in ["rag", "retrieval-augmented", "retrieval augmented"]):
            if any(kw in text for kw in ["improve", "enhancement", "optimization", "architecture"]):
                return TopicCategory.RAG_IMPROVEMENT
            return TopicCategory.RAG_APPLICATION

        if any(kw in text for kw in ["ocr", "optical character", "text recognition"]):
            return TopicCategory.OCR

        if any(kw in text for kw in ["routing", "router", "model selection", "mixture of experts"]):
            return TopicCategory.LLM_ROUTER

        if any(kw in text for kw in ["transformer", "attention", "architecture", "training", "pretraining"]):
            return TopicCategory.LLM_ARCHITECTURE

        if any(kw in text for kw in ["llm", "language model", "gpt", "bert"]):
            return TopicCategory.LLM_APPLICATION

        return TopicCategory.OTHER
