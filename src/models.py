from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Page:
    page_number: int
    text: str


@dataclass
class PolicyDocument:
    document_id: str
    document_name: str
    document_type: str
    pages: List[Page]


@dataclass
class QuestionnaireItem:
    item_id: str
    source_type: str
    question_text: str
    source_document_name: str
    source_page: int
    source_quote: Optional[str] = None


@dataclass
class Citation:
    document_name: str
    page: int
    quote: str


@dataclass
class ValidationResult:
    item_id: str
    question_text: str
    conclusion: str
    confidence: float
    rationale: str
    supporting_citations: List[Citation]
    conflicting_citations: List[Citation]