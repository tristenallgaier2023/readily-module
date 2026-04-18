import os
from dataclasses import dataclass
from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.llm_utils import build_openai_client, parse_json_response
from src.models import Citation, PolicyDocument, QuestionnaireItem, ValidationResult


DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
MAX_RETRIEVED_CHUNKS = 8
MAX_RETURNED_CITATIONS = 5


@dataclass
class CandidateChunk:
    chunk_id: str
    document_name: str
    page: int
    text: str


def validate_items(
    items: List[QuestionnaireItem],
    pnp_docs: List[PolicyDocument],
) -> List[ValidationResult]:
    """
    Validate questionnaire items against the P&P corpus.

    Flow:
    1. Convert P&P pages into candidate chunks.
    2. Retrieve the top relevant chunks for each item using TF-IDF similarity.
    3. Ask the model to classify support / conflict / lack of support.
    4. Return structured validation results.
    """
    if not items:
        return []

    candidate_chunks = build_candidate_chunks(pnp_docs)
    if not candidate_chunks:
        return [
            ValidationResult(
                item_id=item.item_id,
                question_text=item.question_text,
                conclusion="not supported",
                confidence=1.0,
                rationale="No P&P documents were available for validation.",
                supporting_citations=[],
                conflicting_citations=[],
            )
            for item in items
        ]

    client = build_openai_client()
    results: List[ValidationResult] = []

    for item in items:
        retrieved_chunks = retrieve_relevant_chunks(
            question_text=item.question_text,
            candidate_chunks=candidate_chunks,
            top_k=MAX_RETRIEVED_CHUNKS,
        )

        result = classify_item_against_chunks(
            client=client,
            item=item,
            retrieved_chunks=retrieved_chunks,
        )
        results.append(result)

    return results


def build_candidate_chunks(pnp_docs: List[PolicyDocument]) -> List[CandidateChunk]:
    """
    For this demo, use one page = one chunk.
    """
    chunks: List[CandidateChunk] = []

    for doc in pnp_docs:
        for page in doc.pages:
            text = normalize_whitespace(page.text or "")
            if not text:
                continue

            chunks.append(
                CandidateChunk(
                    chunk_id=f"{doc.document_id}_p{page.page_number}",
                    document_name=doc.document_name,
                    page=page.page_number,
                    text=text,
                )
            )

    return chunks


def retrieve_relevant_chunks(
    question_text: str,
    candidate_chunks: List[CandidateChunk],
    top_k: int,
) -> List[CandidateChunk]:
    """
    Retrieve the top candidate chunks using TF-IDF cosine similarity.
    """
    if not candidate_chunks:
        return []

    documents = [question_text] + [chunk.text for chunk in candidate_chunks]

    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(documents)

    question_vector = matrix[0:1]
    chunk_vectors = matrix[1:]

    similarities = cosine_similarity(question_vector, chunk_vectors)[0]
    ranked_indices = similarities.argsort()[::-1]

    retrieved: List[CandidateChunk] = []
    for index in ranked_indices[:top_k]:
        retrieved.append(candidate_chunks[index])

    return retrieved


def classify_item_against_chunks(
    client,
    item: QuestionnaireItem,
    retrieved_chunks: List[CandidateChunk],
) -> ValidationResult:
    """
    Ask the model to determine whether the item is supported, conflicted, or not supported.
    """
    if not retrieved_chunks:
        return ValidationResult(
            item_id=item.item_id,
            question_text=item.question_text,
            conclusion="not supported",
            confidence=1.0,
            rationale="No relevant P&P evidence was retrieved.",
            supporting_citations=[],
            conflicting_citations=[],
        )

    prompt = build_validation_prompt(
        question_text=item.question_text,
        retrieved_chunks=retrieved_chunks,
    )

    response = client.responses.create(
        model=DEFAULT_MODEL,
        input=prompt,
    )

    parsed = parse_json_response(response.output_text.strip())

    conclusion = normalize_conclusion(parsed.get("conclusion"))
    confidence = normalize_confidence(parsed.get("confidence"))
    rationale = str(parsed.get("rationale", "")).strip() or default_rationale(conclusion)

    supporting_indices = normalize_index_list(parsed.get("supporting_chunk_indices", []))
    conflicting_indices = normalize_index_list(parsed.get("conflicting_chunk_indices", []))

    supporting_citations = build_citations_from_indices(
        retrieved_chunks=retrieved_chunks,
        indices=supporting_indices,
        max_citations=MAX_RETURNED_CITATIONS,
    )
    conflicting_citations = build_citations_from_indices(
        retrieved_chunks=retrieved_chunks,
        indices=conflicting_indices,
        max_citations=MAX_RETURNED_CITATIONS,
    )

    return ValidationResult(
        item_id=item.item_id,
        question_text=item.question_text,
        conclusion=conclusion,
        confidence=confidence,
        rationale=rationale,
        supporting_citations=supporting_citations,
        conflicting_citations=conflicting_citations,
    )


def build_validation_prompt(
    question_text: str,
    retrieved_chunks: List[CandidateChunk],
) -> str:
    chunk_payload = [
        {
            "chunk_index": index,
            "document_name": chunk.document_name,
            "page": chunk.page,
            "text": chunk.text,
        }
        for index, chunk in enumerate(retrieved_chunks)
    ]

    return f"""
You are validating whether a health plan P&P supports a regulatory questionnaire item.

Task:
- Review the questionnaire item.
- Review the candidate P&P excerpts.
- Determine whether the item is:
  - "supported" if the evidence clearly supports the requirement and there is no meaningful contradiction
  - "conflicted" if there is both supporting and conflicting evidence or an apparent contradiction
  - "not supported" if the requirement is not supported by the evidence

Important:
- Be conservative.
- Exact wording is not required if the meaning is clearly equivalent.
- If one excerpt supports the requirement and another excerpt materially contradicts it, return "conflicted".
- Only cite chunks that actually matter to the determination.
- Return JSON only.

Return exactly this JSON shape:
{{
  "conclusion": "supported" | "conflicted" | "not supported",
  "confidence": 0.0,
  "rationale": "1 to 2 sentence explanation",
  "supporting_chunk_indices": [0],
  "conflicting_chunk_indices": [1]
}}

Questionnaire item:
{question_text}

Candidate P&P excerpts:
{chunk_payload}
""".strip()


def build_citations_from_indices(
    retrieved_chunks: List[CandidateChunk],
    indices: List[int],
    max_citations: int,
) -> List[Citation]:
    citations: List[Citation] = []

    for index in indices[:max_citations]:
        if index < 0 or index >= len(retrieved_chunks):
            continue

        chunk = retrieved_chunks[index]
        citations.append(
            Citation(
                document_name=chunk.document_name,
                page=chunk.page,
                quote=chunk.text,
            )
        )

    return citations


def normalize_conclusion(value) -> str:
    text = str(value).strip().lower()

    if text == "supported":
        return "supported"
    if text == "conflicted":
        return "conflicted"
    return "not supported"


def normalize_confidence(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, min(1.0, number))


def normalize_index_list(value) -> List[int]:
    if not isinstance(value, list):
        return []

    indices: List[int] = []
    for item in value:
        try:
            indices.append(int(item))
        except (TypeError, ValueError):
            continue

    return indices


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split()).strip()


def default_rationale(conclusion: str) -> str:
    if conclusion == "supported":
        return "Retrieved P&P evidence appears to support the questionnaire item."
    if conclusion == "conflicted":
        return "Retrieved P&P evidence includes both supporting and conflicting language."
    return "Retrieved P&P evidence does not appear to support the questionnaire item."