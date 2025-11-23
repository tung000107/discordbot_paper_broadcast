"""Type definitions for agent system."""
from enum import Enum
from typing import Optional
from dataclasses import dataclass
from datetime import datetime


class TopicCategory(str, Enum):
    """Paper topic categories for classification."""
    LLM_ARCHITECTURE = "LLM架構"
    LLM_APPLICATION = "LLM應用"
    RAG_IMPROVEMENT = "RAG改良"
    RAG_APPLICATION = "RAG應用"
    OCR = "OCR"
    LLM_ROUTER = "LLM Router"
    OTHER = "其他"


@dataclass
class PaperCandidate:
    """Paper candidate from retrieval agent."""
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    published: datetime
    primary_category: str
    pdf_url: str
    entry_url: str

    # Citation data (from Semantic Scholar)
    citation_count: int = 0
    influential_citation_count: int = 0

    # Metadata
    source: str = "arxiv"  # arxiv, conference, etc.
    conference_name: Optional[str] = None


@dataclass
class RankedPaper:
    """Paper with ranking score and summary."""
    candidate: PaperCandidate
    score: float
    topic: TopicCategory
    summary: Optional[dict] = None  # Summary from LLM pipeline

    @property
    def arxiv_id(self) -> str:
        return self.candidate.arxiv_id

    @property
    def title(self) -> str:
        return self.candidate.title
