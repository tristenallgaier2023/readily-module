import json
import os
from typing import List, Optional

from openai import OpenAI

from src.models import QuestionnaireItem


def build_openai_client() -> OpenAI:
    api_key = get_api_key()
    if api_key:
        return OpenAI(api_key=api_key)
    return OpenAI()


def get_api_key() -> Optional[str]:
    try:
        import streamlit as st

        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass

    return os.getenv("OPENAI_API_KEY")


def chunk_pages(pages, window_size: int):
    for start in range(0, len(pages), window_size):
        yield pages[start : start + window_size]


def parse_json_response(raw_text: str) -> dict:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw_text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return {"items": []}


def infer_page_for_question(question_text: str, page_payload: List[dict]) -> Optional[int]:
    normalized_question = normalize_for_match(question_text)

    best_page = None
    best_overlap = 0

    question_terms = set(normalized_question.split())

    for page in page_payload:
        page_terms = set(normalize_for_match(page["text"]).split())
        overlap = len(question_terms & page_terms)

        if overlap > best_overlap:
            best_overlap = overlap
            best_page = page["page_number"]

    return best_page


def clean_question_text(text: str) -> str:
    return " ".join(text.split()).strip()


def normalize_for_match(text: str) -> str:
    cleaned = []
    for char in text.lower():
        if char.isalnum() or char.isspace():
            cleaned.append(char)
        else:
            cleaned.append(" ")
    return " ".join("".join(cleaned).split())


def deduplicate_items(items: List[QuestionnaireItem]) -> List[QuestionnaireItem]:
    deduped = {}
    ordered_keys = []

    for item in items:
        key = normalize_for_match(item.question_text)
        if not key:
            continue

        if key not in deduped:
            deduped[key] = item
            ordered_keys.append(key)
            continue

        existing = deduped[key]
        if item.source_page < existing.source_page:
            deduped[key] = item

    return [deduped[key] for key in ordered_keys]