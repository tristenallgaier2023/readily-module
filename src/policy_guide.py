import os
from typing import List

from src.llm_utils import (
    build_openai_client,
    chunk_pages,
    clean_question_text,
    deduplicate_items,
    infer_page_for_question,
    parse_json_response,
)
from src.models import PolicyDocument, QuestionnaireItem


DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
PAGES_PER_WINDOW = 3


def extract_items_from_policy_guide(document: PolicyDocument) -> List[QuestionnaireItem]:
    """
    Extract questionnaire-like checks from a Policy Guide.

    Strategy:
    1. Process the guide in small page windows.
    2. Ask the model to identify concrete obligations.
    3. Normalize each obligation into a questionnaire item.
    4. Deduplicate similar items across windows.
    """
    if not document.pages:
        return []

    client = build_openai_client()
    all_items: List[QuestionnaireItem] = []

    page_windows = chunk_pages(document.pages, PAGES_PER_WINDOW)

    for window in page_windows:
        extracted = _extract_items_from_window(
            client=client,
            document=document,
            pages=window,
        )
        all_items.extend(extracted)

    return deduplicate_items(all_items)


def _extract_items_from_window(
    client,
    document: PolicyDocument,
    pages,
) -> List[QuestionnaireItem]:
    page_payload = [
        {
            "page_number": page.page_number,
            "text": page.text,
        }
        for page in pages
        if page.text.strip()
    ]

    if not page_payload:
        return []

    prompt = _build_extraction_prompt(page_payload)

    response = client.responses.create(
        model=DEFAULT_MODEL,
        input=prompt,
    )

    raw_text = response.output_text.strip()
    parsed = parse_json_response(raw_text)

    items: List[QuestionnaireItem] = []
    raw_items = parsed.get("items", [])

    for index, raw_item in enumerate(raw_items):
        question_text = str(raw_item.get("question_text", "")).strip()
        source_page = raw_item.get("source_page")
        source_quote = str(raw_item.get("source_quote", "")).strip() or None

        if not question_text:
            continue

        question_text = clean_question_text(question_text)
        if not question_text.endswith("?"):
            question_text = question_text.rstrip(".") + "?"

        if not isinstance(source_page, int):
            source_page = infer_page_for_question(question_text, page_payload)

        if source_page is None:
            source_page = pages[0].page_number

        item_id = f"{document.document_id}_p{source_page}_pg{index + 1}"

        items.append(
            QuestionnaireItem(
                item_id=item_id,
                source_type="policy_guide",
                question_text=question_text,
                source_document_name=document.document_name,
                source_page=source_page,
                source_quote=source_quote,
            )
        )

    return items


def _build_extraction_prompt(page_payload: List[dict]) -> str:
    return f"""
You are extracting compliance obligations from a regulatory Policy Guide and converting them into questionnaire items.

Your job:
- Identify every concrete obligation, requirement, or compliance expectation stated in the provided pages.
- Only extract obligations that could reasonably be validated against a health plan's internal P&P documents.
- Ignore introductory, descriptive, historical, or purely contextual text unless it contains a concrete requirement.
- Convert each obligation into a single questionnaire item phrased like a compliance review question.
- Preserve the meaning of the requirement closely.
- Do not combine distinct obligations into one item if they can be checked separately.
- Return JSON only.

Questionnaire item guidance:
- Phrase each output as a yes/no style compliance question.
- Good example: "Does the P&P state that retrospective review requests will be responded to within 14 calendar days?"
- Good example: "Does the P&P state that in-network hospice services should be initiated within 24 hours of a request when clinically appropriate?"
- Avoid vague wording like "Does the plan comply with the policy guide?"

Return exactly this JSON shape:
{{
  "items": [
    {{
      "question_text": "Does the P&P state that ...?",
      "source_page": 3,
      "source_quote": "short exact quote from the source supporting the extraction"
    }}
  ]
}}

Pages:
{page_payload}
""".strip()