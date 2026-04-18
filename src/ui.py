from pathlib import Path
from typing import List

import streamlit as st

from src.ingest import extract_pdf_pages, load_policy_documents
from src.models import PolicyDocument, QuestionnaireItem, ValidationResult
from src.policy_guide import extract_items_from_policy_guide
from src.questionnaire import parse_questionnaire
from src.validate import validate_items


P_AND_P_FOLDER = Path("sample_docs/p_and_ps")


def render_app() -> None:
    initialize_session_state()

    render_intro()
    render_input_type_section()
    render_pnp_status()
    render_upload_section()
    render_item_generation_section()
    render_item_review_section()
    render_validation_section()
    render_results_section()


def initialize_session_state() -> None:
    defaults = {
        "input_type": "Questionnaire",
        "uploaded_document": None,
        "generated_items": [],
        "approved_items": [],
        "validation_results": [],
        "pnp_docs": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


@st.cache_data(show_spinner=False)
def load_pnp_corpus(folder_path: str) -> List[PolicyDocument]:
    return load_policy_documents(folder_path)


def build_uploaded_document(uploaded_file, document_type: str) -> PolicyDocument:
    pages = extract_pdf_pages(uploaded_file)

    return PolicyDocument(
        document_id=f"uploaded_{uploaded_file.name}",
        document_name=uploaded_file.name,
        document_type=document_type,
        pages=pages,
    )


def generate_questionnaire_items(
    document: PolicyDocument,
    input_type: str,
) -> List[QuestionnaireItem]:
    if input_type == "Questionnaire":
        return parse_questionnaire(document)
    return extract_items_from_policy_guide(document)

def on_input_type_change() -> None:
    st.session_state.uploaded_document = None
    reset_downstream_state()


def reset_downstream_state() -> None:
    st.session_state.generated_items = []
    st.session_state.approved_items = []
    st.session_state.validation_results = []


def render_intro() -> None:
    st.title("Policy Compliance Validator")

    st.write(
        "This tool helps you answer regulatory questionnaires by identifying and "
        "validating questionnaire items against your P&P documents."
    )

    st.write(
        'A questionnaire item is a single compliance check. For example: '
        '"Does your P&P state that you will respond to retrospective requests '
        'within 14 days?"'
    )

    st.write("You can generate questionnaire items in two ways:")

    st.markdown(
        "- **Upload a questionnaire**: Items are extracted directly from the Submission Review Form.\n"
        "- **Upload a Policy Guide**: Regulatory obligations are extracted and converted into "
        "**predicted questionnaire items**, modeling the types of questions that would later "
        "appear in a questionnaire."
    )

    st.write(
        "After items are generated, you can review and approve them, then validate each item "
        "against your P&Ps to automatically identify supporting and/or conflicting evidence."
    )


def render_input_type_section() -> None:
    st.subheader("1. Select input type")

    st.radio(
        "What are you uploading?",
        options=["Questionnaire", "Policy Guide"],
        key="input_type",
        horizontal=True,
        on_change=on_input_type_change,
    )

    st.caption(f"Selected input type: {st.session_state.input_type}")


def render_pnp_status() -> None:
    st.subheader("2. P&P corpus")

    st.write(f"Using local P&P folder: `{P_AND_P_FOLDER}`")

    if st.session_state.pnp_docs is None:
        with st.spinner("Loading P&P documents..."):
            st.session_state.pnp_docs = load_pnp_corpus(str(P_AND_P_FOLDER))

    st.success(f"Loaded {len(st.session_state.pnp_docs)} P&P document(s)")


def render_upload_section() -> None:
    st.subheader("3. Upload regulatory input")

    if st.session_state.input_type is None:
        st.info("Select an input type to continue.")
        return

    help_text = (
        "Upload the Submission Review Form PDF."
        if st.session_state.input_type == "Questionnaire"
        else "Upload the Policy Guide PDF."
    )

    uploaded_file = st.file_uploader(
        "Upload PDF",
        type=["pdf"],
        help=help_text,
    )

    if uploaded_file is None:
        return

    current_name = getattr(st.session_state.uploaded_document, "document_name", None)
    if current_name != uploaded_file.name:
        document_type = (
            "submission_review_form"
            if st.session_state.input_type == "Questionnaire"
            else "policy_guide"
        )
        st.session_state.uploaded_document = build_uploaded_document(
            uploaded_file=uploaded_file,
            document_type=document_type,
        )
        reset_downstream_state()

    uploaded_doc = st.session_state.uploaded_document
    st.success(f"Uploaded: {uploaded_doc.document_name}")
    st.caption(f"Extracted {len(uploaded_doc.pages)} page(s)")


def render_item_generation_section() -> None:
    st.subheader("4. Generate questionnaire items")

    uploaded_doc = st.session_state.uploaded_document
    if uploaded_doc is None:
        st.info("Upload a document to continue.")
        return

    if st.button("Generate items", type="primary"):
        with st.spinner("Generating questionnaire items..."):
            st.session_state.generated_items = generate_questionnaire_items(
                document=uploaded_doc,
                input_type=st.session_state.input_type,
            )
            st.session_state.approved_items = []
            st.session_state.validation_results = []

    generated_items = st.session_state.generated_items
    if not generated_items:
        return

    st.success(f"Generated {len(generated_items)} item(s)")


def render_item_review_section() -> None:
    st.subheader("5. Review and approve items")

    generated_items: List[QuestionnaireItem] = st.session_state.generated_items
    if not generated_items:
        st.info("Generate items to review them here.")
        return

    review_mode = st.radio(
        "Approval mode",
        options=["Approve all", "Review individually"],
        horizontal=True,
    )

    approved_items: List[QuestionnaireItem] = []

    if review_mode == "Approve all":
        approved_items = generated_items
        st.caption("All generated items will be passed to validation.")
    else:
        for index, item in enumerate(generated_items):
            with st.expander(f"Item {index + 1}: {item.question_text}", expanded=False):
                include_item = st.checkbox(
                    "Include item",
                    key=f"include_item_{item.item_id}",
                    value=True,
                )

                edited_text = st.text_area(
                    "Question text",
                    value=item.question_text,
                    key=f"question_text_{item.item_id}",
                    height=100,
                )

                source_bits = []
                if getattr(item, "source_document_name", None):
                    source_bits.append(f"Source doc: {item.source_document_name}")
                if getattr(item, "source_page", None) is not None:
                    source_bits.append(f"Page: {item.source_page}")
                if source_bits:
                    st.caption(" | ".join(source_bits))

                source_quote = getattr(item, "source_quote", None)
                if source_quote:
                    st.markdown("**Source quote**")
                    st.write(source_quote)

                if include_item:
                    approved_items.append(
                        QuestionnaireItem(
                            item_id=item.item_id,
                            source_type=item.source_type,
                            question_text=edited_text,
                            source_document_name=item.source_document_name,
                            source_page=item.source_page,
                            source_quote=getattr(item, "source_quote", None),
                        )
                    )

    st.session_state.approved_items = approved_items
    st.write(f"Approved items: {len(approved_items)}")


def render_validation_section() -> None:
    st.subheader("6. Validate against P&Ps")

    approved_items: List[QuestionnaireItem] = st.session_state.approved_items
    pnp_docs: List[PolicyDocument] = st.session_state.pnp_docs

    if not approved_items:
        st.info("Approve at least one item to run validation.")
        return

    if st.button("Run validation", type="primary"):
        with st.spinner("Validating questionnaire items against P&Ps..."):
            st.session_state.validation_results = validate_items(
                items=approved_items,
                pnp_docs=pnp_docs,
            )

    validation_results: List[ValidationResult] = st.session_state.validation_results
    if validation_results:
        st.success(f"Validation complete for {len(validation_results)} item(s)")


def render_results_section() -> None:
    st.subheader("7. Results")

    results: List[ValidationResult] = st.session_state.validation_results
    if not results:
        st.info("Run validation to see results.")
        return

    for index, result in enumerate(results):
        with st.expander(f"Result {index + 1}: {result.question_text}", expanded=False):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"**Conclusion:** {result.conclusion}")
                st.markdown(f"**Rationale:** {result.rationale}")

            with col2:
                st.metric("Confidence", f"{result.confidence:.2f}")

            supporting_col, conflicting_col = st.columns(2)

            with supporting_col:
                render_citation_list(
                    "Top supporting citations",
                    result.supporting_citations,
                )

            with conflicting_col:
                render_citation_list(
                    "Top conflicting citations",
                    result.conflicting_citations,
                )


def render_citation_list(title: str, citations) -> None:
    st.markdown(f"**{title}**")

    if not citations:
        st.write("None")
        return

    for citation in citations:
        st.markdown(f"**{citation.document_name}**, p. {citation.page}")
        st.write(citation.quote)