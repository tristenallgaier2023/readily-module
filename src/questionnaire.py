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
PAGES_PER_WINDOW = 4


def parse_questionnaire(document: PolicyDocument) -> List[QuestionnaireItem]:
    """
    Parse a questionnaire PDF into questionnaire items using an LLM.

    Strategy:
    1. Process the questionnaire in small page windows to reduce missed items.
    2. Ask the model to extract every distinct questionnaire item exactly as written.
    3. Deduplicate while preserving source page attribution.
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

        if not isinstance(source_page, int):
            source_page = infer_page_for_question(question_text, page_payload)

        if source_page is None:
            source_page = pages[0].page_number

        item_id = f"{document.document_id}_p{source_page}_q{index + 1}"

        items.append(
            QuestionnaireItem(
                item_id=item_id,
                source_type="questionnaire",
                question_text=question_text,
                source_document_name=document.document_name,
                source_page=source_page,
                source_quote=source_quote,
            )
        )

    return items


def _build_extraction_prompt(page_payload: List[dict]) -> str:
    return f"""
You are extracting questionnaire items from a regulatory submission questionnaire.

Your job:
- Extract every distinct questionnaire item from the provided pages.
- A questionnaire item is a single compliance question or yes/no style check.
- Preserve the question wording as closely as possible.
- Do not summarize.
- Do not combine multiple distinct questions into one.
- Include wrapped questions that span multiple lines.
- Ignore headers, footers, page numbers, section titles, instructions, and answer fields unless they are part of the actual question text.
- If a question is phrased as a statement check rather than ending with a question mark, still include it.
- Return JSON only.

Return exactly this JSON shape:
{{
  "items": [
    {{
      "question_text": "full question text",
      "source_page": 3,
      "source_quote": "short exact quote from the source supporting the extraction"
    }}
  ]
}}

Pages:
{page_payload}
""".strip()