import pandas as pd
import streamlit as st


def _confidence_badge(issue: dict | None) -> str:
    if not issue:
        return ""
    c = issue.get("confidence", 1.0)
    return " 🔴" if c < 0.5 else " 🟡"


def _show_issue(issue: dict | None):
    if issue:
        c = issue.get("confidence", 1.0)
        color = "red" if c < 0.5 else "orange"
        st.markdown(
            f"<small style='color:{color}'>⚠️ {issue['issue']} ({c:.0%} confidence)</small>",
            unsafe_allow_html=True,
        )


def _render_key_value(section: dict, issue: dict | None, key: str) -> dict:
    title = section.get("title")
    if title:
        st.markdown(f"**{title}**{_confidence_badge(issue)}")
    _show_issue(issue)

    pairs = section.get("pairs") or []
    edited_pairs = []

    for j, pair in enumerate(pairs):
        col_label, col_val = st.columns([1, 2])
        with col_label:
            st.markdown(
                f"<div style='padding:6px 0; color:#555; font-size:0.9em'>{pair.get('key', '')}</div>",
                unsafe_allow_html=True,
            )
        with col_val:
            val = st.text_input(
                label=pair.get("key", ""),
                value=str(pair.get("value", "") or ""),
                key=f"{key}.kv{j}",
                label_visibility="collapsed",
            )
        edited_pairs.append({"key": pair.get("key", ""), "value": val})

    return {**section, "pairs": edited_pairs}


def _render_table(section: dict, issue: dict | None, key: str) -> dict:
    title = section.get("title")
    if title:
        st.markdown(f"**{title}**{_confidence_badge(issue)}")
    _show_issue(issue)

    columns = section.get("columns") or []
    rows = section.get("rows") or []

    if columns:
        df = pd.DataFrame(rows, columns=columns)
    else:
        df = pd.DataFrame(rows)

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key=key,
    )

    return {
        **section,
        "columns": list(edited_df.columns),
        "rows": edited_df.values.tolist(),
    }


def _render_qa_pair(section: dict, issue: dict | None, key: str) -> dict:
    title = section.get("title")
    if title:
        st.markdown(f"**{title}**{_confidence_badge(issue)}")
    _show_issue(issue)

    items = section.get("items") or []
    edited_items = []

    for j, item in enumerate(items):
        q = item.get("question", "")
        st.markdown(f"<div style='font-weight:600; margin-top:8px'>{q}</div>", unsafe_allow_html=True)
        answer = st.text_area(
            label=q,
            value=str(item.get("answer", "") or ""),
            key=f"{key}.qa{j}",
            label_visibility="collapsed",
            height=100,
        )
        edited_items.append({"question": q, "answer": answer})
        st.divider()

    return {**section, "items": edited_items}


def _render_paragraph(section: dict, issue: dict | None, key: str) -> dict:
    title = section.get("title")
    label = (title or "Text") + _confidence_badge(issue)
    if title:
        st.markdown(f"**{title}**{_confidence_badge(issue)}")
    _show_issue(issue)

    text = st.text_area(
        label=label,
        value=str(section.get("text", "") or ""),
        key=key,
        label_visibility="collapsed",
        height=150,
    )

    return {**section, "text": text}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_document(doc: dict, issues_map: dict, key_prefix: str) -> dict:
    """
    Render a document structure as an editable Streamlit form.

    Args:
        doc:        document dict with keys: doc_type, title, sections
        issues_map: dict[section_index (int), issue_info (dict)]
        key_prefix: stable Streamlit widget key prefix

    Returns:
        edited document dict (same structure as doc)
    """
    RENDERERS = {
        "key_value": _render_key_value,
        "table":     _render_table,
        "qa_pair":   _render_qa_pair,
        "paragraph": _render_paragraph,
    }

    edited_sections = []

    for i, section in enumerate(doc.get("sections", [])):
        stype = section.get("type", "paragraph")
        section_key = f"{key_prefix}.s{i}"
        issue = issues_map.get(i)

        render_fn = RENDERERS.get(stype, _render_paragraph)
        edited_section = render_fn(section, issue, section_key)
        edited_sections.append(edited_section)

        if i < len(doc.get("sections", [])) - 1:
            st.markdown("<hr style='margin:12px 0; border-color:#eee'>", unsafe_allow_html=True)

    return {
        "doc_type": doc.get("doc_type", "other"),
        "title":    doc.get("title", ""),
        "sections": edited_sections,
    }


def build_issues_map(section_issues: list) -> dict:
    """Convert section_issues list to a dict keyed by section_index."""
    return {issue["section_index"]: issue for issue in (section_issues or []) if "section_index" in issue}
