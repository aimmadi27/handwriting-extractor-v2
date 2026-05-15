import json
import tempfile
from copy import deepcopy

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from pdf2image import convert_from_bytes

from auth import get_current_user, handle_oauth_callback, logout, start_google_login
from llm_handler import LLMHandler
from orchestrator import Orchestrator
from renderer import build_issues_map, render_document
from exporters.pdf_export import export_pdf
from exporters.word_export import export_word
from exporters.excel_export import export_excel

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Form Extractor v2",
    page_icon="🤖",
    layout="wide",
)
load_dotenv()

DOC_TYPE_LABELS = {
    "form":       "Form",
    "receipt":    "Receipt",
    "letter":     "Letter",
    "assessment": "Assessment / Exam",
    "bank_slip":  "Bank Slip",
    "invoice":    "Invoice",
    "notes":      "Notes",
    "other":      "Other",
}

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def init_state():
    st.session_state.pdf_pages      = None
    st.session_state.pdf_bytes      = None
    st.session_state.last_pdf       = None
    st.session_state.selected_pages = set()
    st.session_state.pages_confirmed     = False
    st.session_state.extraction_complete = False
    st.session_state.page_results   = {}
    st.session_state.review_data    = {}

if "initialized" not in st.session_state:
    init_state()
    st.session_state.initialized = True

# ---------------------------------------------------------------------------
# Google OAuth gate
# ---------------------------------------------------------------------------

q = st.query_params
user = None

if "code" in q and "state" in q:
    user = handle_oauth_callback()
if not user:
    user = get_current_user()

if not user:
    st.title("Sign in to continue")
    st.caption("Use your Google account.")
    if "_auth_url" not in st.session_state:
        st.session_state["_auth_url"] = start_google_login()
    st.link_button("Continue with Google", st.session_state["_auth_url"], type="primary")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    if user.picture:
        st.image(user.picture, width=60)
    st.markdown(f"**{user.name}**")
    st.caption(user.email)
    st.divider()
    uploaded_pdf = st.file_uploader("📤 Upload document (PDF)", type=["pdf"])
    if st.button("Log out"):
        logout()
        st.rerun()

# Reset state on new file
if uploaded_pdf and uploaded_pdf.name != st.session_state.last_pdf:
    init_state()
    pdf_bytes = uploaded_pdf.getvalue()
    pages = convert_from_bytes(pdf_bytes, dpi=150)
    st.session_state.pdf_bytes      = pdf_bytes
    st.session_state.pdf_pages      = pages
    st.session_state.last_pdf       = uploaded_pdf.name
    st.session_state.selected_pages = set(range(1, len(pages) + 1))

# ---------------------------------------------------------------------------
# LLM + Orchestrator
# ---------------------------------------------------------------------------

st.title("🤖 Handwritten Document Extractor")

try:
    llm = LLMHandler()
    orchestrator = Orchestrator(llm)
except Exception as e:
    st.error(f"Failed to initialise LLM: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_upload, tab_extract, tab_review, tab_export = st.tabs([
    "📤 Upload",
    "⚙️ Extract",
    "✏️ Review",
    "📥 Export",
])

# ===========================================================================
# Tab 1 — Upload & page selection
# ===========================================================================

with tab_upload:
    if not uploaded_pdf:
        st.info("Upload a PDF using the sidebar to begin.")
        st.stop()

    pages = st.session_state.pdf_pages
    st.success(f"Loaded **{uploaded_pdf.name}** — {len(pages)} page(s)")

    st.subheader("Select pages to process")

    col1, col2, _ = st.columns([1, 1, 6])
    with col1:
        if st.button("Select All"):
            st.session_state.selected_pages = set(range(1, len(pages) + 1))
            for p in range(1, len(pages) + 1):
                st.session_state[f"psel_{p}"] = True
            st.session_state.pages_confirmed = False
            st.rerun()
    with col2:
        if st.button("Deselect All"):
            st.session_state.selected_pages = set()
            for p in range(1, len(pages) + 1):
                st.session_state[f"psel_{p}"] = False
            st.session_state.pages_confirmed = False
            st.rerun()

    new_sel = set(st.session_state.selected_pages)
    cols = st.columns(3)
    for idx, page_num in enumerate(range(1, len(pages) + 1)):
        with cols[idx % 3]:
            st.image(pages[page_num - 1], caption=f"Page {page_num}", use_container_width=True)
            checked = st.checkbox(
                f"Include Page {page_num}",
                value=(page_num in st.session_state.selected_pages),
                key=f"psel_{page_num}",
                disabled=st.session_state.pages_confirmed,
            )
            if checked:
                new_sel.add(page_num)
            else:
                new_sel.discard(page_num)

    if not st.session_state.pages_confirmed:
        if st.button("✅ Confirm Pages", type="primary"):
            if not new_sel:
                st.warning("Select at least one page.")
            else:
                st.session_state.selected_pages = new_sel
                st.session_state.pages_confirmed = True
                st.rerun()
    else:
        st.success(f"Pages confirmed: {sorted(st.session_state.selected_pages)}")
        if st.button("Change selection"):
            st.session_state.pages_confirmed    = False
            st.session_state.extraction_complete = False
            st.rerun()


# ===========================================================================
# Tab 2 — Extraction
# ===========================================================================

with tab_extract:
    if not st.session_state.pages_confirmed:
        st.info("Confirm page selection in the Upload tab first.")
        st.stop()

    pages    = st.session_state.pdf_pages
    selected = sorted(st.session_state.selected_pages)

    if not st.session_state.extraction_complete:
        st.markdown(
            "The **Parser Agent** reads each page, identifies the document type, "
            "and extracts the full content into a structured digital document. "
            "The **Validator Agent** then checks and scores the output."
        )

        if st.button("🚀 Run Extraction", type="primary"):
            progress   = st.progress(0)
            status     = st.empty()
            agent_info = st.empty()

            def on_progress(page_num, stage):
                labels = {"parsing": "🔍 Parsing", "validating": "✅ Validating"}
                agent_info.info(f"Page {page_num}: {labels.get(stage, stage)}...")

            results = {}
            for idx, page_num in enumerate(selected, start=1):
                status.write(f"Processing page {page_num} of {len(selected)}...")
                page_img = pages[page_num - 1]

                with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
                    page_img.save(tmp.name, "PNG")
                    img_bytes = open(tmp.name, "rb").read()

                results[page_num] = orchestrator.run_page(img_bytes, page_num, on_progress)
                progress.progress(idx / len(selected))

            agent_info.empty()
            status.empty()

            st.session_state.page_results = results
            st.session_state.review_data  = {
                pn: {
                    "doc_type": r["doc_type"],
                    "title":    r["title"],
                    "sections": deepcopy(r["sections"]),
                }
                for pn, r in results.items()
            }
            st.session_state.extraction_complete = True
            st.rerun()

    else:
        st.success("Extraction complete.")

        # Summary table
        rows = []
        for pn, r in st.session_state.page_results.items():
            val = r.get("validation", {})
            rows.append({
                "Page":                pn,
                "Document Type":       DOC_TYPE_LABELS.get(r.get("doc_type", ""), r.get("doc_type", "")),
                "Title":               r.get("title", ""),
                "Overall Confidence":  f"{val.get('overall_confidence', 1.0):.0%}",
                "Issues":              len(val.get("section_issues", [])),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if st.button("🔄 Re-run Extraction"):
            st.session_state.extraction_complete = False
            st.session_state.review_data = {}
            st.rerun()


# ===========================================================================
# Tab 3 — Review (side-by-side)
# ===========================================================================

with tab_review:
    if not st.session_state.extraction_complete:
        st.info("Run extraction first.")
        st.stop()

    results     = st.session_state.page_results
    review_data = st.session_state.review_data
    pages       = st.session_state.pdf_pages

    available = sorted(results.keys())
    selected_page = st.selectbox(
        "Select page",
        available,
        format_func=lambda p: (
            f"Page {p} — "
            f"{DOC_TYPE_LABELS.get(results[p].get('doc_type',''), results[p].get('doc_type',''))} "
            f"| {results[p].get('title', '')}"
        ),
    )

    result     = results[selected_page]
    validation = result.get("validation", {})
    conf       = validation.get("overall_confidence", 1.0)
    issues     = validation.get("section_issues", [])
    issues_map = build_issues_map(issues)

    # Confidence bar
    conf_color = "green" if conf >= 0.8 else ("orange" if conf >= 0.5 else "red")
    st.markdown(
        f"Confidence: :{conf_color}[**{conf:.0%}**] &nbsp; Issues: **{len(issues)}**",
        unsafe_allow_html=False,
    )

    if issues:
        with st.expander("View validation issues"):
            st.dataframe(
                pd.DataFrame(issues)[["section_index", "issue", "confidence"]],
                use_container_width=True,
                hide_index=True,
            )

    st.divider()

    # Side-by-side layout
    col_img, col_doc = st.columns([2, 3])

    with col_img:
        st.markdown("**Original**")
        st.image(pages[selected_page - 1], use_container_width=True)

    with col_doc:
        st.markdown("**Digital Version**")

        current = review_data.get(selected_page, {
            "doc_type": result["doc_type"],
            "title":    result["title"],
            "sections": result["sections"],
        })

        edited = render_document(current, issues_map, f"rv.p{selected_page}")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Save Changes", key=f"save_{selected_page}"):
                st.session_state.review_data[selected_page] = edited
                st.success("Saved.")
        with c2:
            if st.button("↩️ Reset to Extracted", key=f"reset_{selected_page}"):
                st.session_state.review_data[selected_page] = {
                    "doc_type": result["doc_type"],
                    "title":    result["title"],
                    "sections": deepcopy(result["sections"]),
                }
                st.rerun()


# ===========================================================================
# Tab 4 — Export
# ===========================================================================

with tab_export:
    if not st.session_state.extraction_complete:
        st.info("Complete extraction first.")
        st.stop()

    review_data = st.session_state.review_data
    file_stem   = (st.session_state.last_pdf or "document").rsplit(".", 1)[0]

    if not review_data:
        st.info("No data to export yet.")
        st.stop()

    st.subheader("📥 Export")

    # Quick preview of what will be exported
    with st.expander("Preview extracted content"):
        st.json(review_data, expanded=False)

    st.divider()

    col_pdf, col_word, col_excel, col_json = st.columns(4)

    with col_pdf:
        st.markdown("**PDF**")
        if st.button("Generate PDF"):
            with st.spinner("Building PDF..."):
                try:
                    pdf_bytes = export_pdf(review_data)
                    st.download_button(
                        "⬇️ Download PDF",
                        data=pdf_bytes,
                        file_name=f"{file_stem}.pdf",
                        mime="application/pdf",
                    )
                except Exception as e:
                    st.error(f"PDF export failed: {e}")

    with col_word:
        st.markdown("**Word (.docx)**")
        if st.button("Generate Word"):
            with st.spinner("Building Word doc..."):
                try:
                    docx_bytes = export_word(review_data)
                    st.download_button(
                        "⬇️ Download Word",
                        data=docx_bytes,
                        file_name=f"{file_stem}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                except Exception as e:
                    st.error(f"Word export failed: {e}")

    with col_excel:
        st.markdown("**Excel (.xlsx)**")
        if st.button("Generate Excel"):
            with st.spinner("Building Excel..."):
                try:
                    xlsx_bytes = export_excel(review_data)
                    st.download_button(
                        "⬇️ Download Excel",
                        data=xlsx_bytes,
                        file_name=f"{file_stem}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                except Exception as e:
                    st.error(f"Excel export failed: {e}")

    with col_json:
        st.markdown("**JSON**")
        st.download_button(
            "⬇️ Download JSON",
            data=json.dumps(review_data, indent=2, ensure_ascii=False),
            file_name=f"{file_stem}.json",
            mime="application/json",
        )
