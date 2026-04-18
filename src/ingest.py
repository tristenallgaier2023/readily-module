from pathlib import Path
from typing import BinaryIO, List, Union

from pypdf import PdfReader

from src.models import Page, PolicyDocument


PdfInput = Union[str, Path, BinaryIO]


def extract_pdf_pages(pdf_source: PdfInput) -> List[Page]:
    """
    Extract page-level text from a PDF source.

    Supports:
    - Streamlit uploaded files
    - file-like objects
    - local file paths
    """
    reader = PdfReader(pdf_source)
    pages: List[Page] = []

    for index, pdf_page in enumerate(reader.pages):
        text = pdf_page.extract_text() or ""
        pages.append(
            Page(
                page_number=index + 1,
                text=text.strip(),
            )
        )

    return pages


def load_policy_documents(folder_path: Union[str, Path]) -> List[PolicyDocument]:
    """
    Load all PDF policy documents from a local folder.
    """
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Policy folder not found: {folder}")

    documents: List[PolicyDocument] = []

    for pdf_path in sorted(folder.rglob("*.pdf")):
        pages = extract_pdf_pages(pdf_path)

        documents.append(
            PolicyDocument(
                document_id=pdf_path.stem,
                document_name=pdf_path.name,
                document_type="p_and_p",
                pages=pages,
            )
        )

    return documents