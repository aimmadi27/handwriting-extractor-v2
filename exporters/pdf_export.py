import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)


def export_pdf(page_results: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    label_style = ParagraphStyle(
        "Label", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=9, textColor=colors.HexColor("#444444"),
    )
    value_style = ParagraphStyle(
        "Value", parent=styles["Normal"],
        fontName="Helvetica", fontSize=10,
    )
    question_style = ParagraphStyle(
        "Question", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=10, spaceAfter=2,
    )
    answer_style = ParagraphStyle(
        "Answer", parent=styles["Normal"],
        fontName="Helvetica", fontSize=10, leftIndent=12,
    )

    story = []

    for page_num in sorted(page_results.keys()):
        page = page_results[page_num]

        story.append(Paragraph(page.get("title", f"Page {page_num}"), styles["Title"]))
        doc_type = page.get("doc_type", "")
        if doc_type:
            story.append(Paragraph(doc_type.upper(), styles["Heading4"]))
        story.append(Spacer(1, 0.4 * cm))

        for section in page.get("sections", []):
            stype = section.get("type")
            title = section.get("title")

            if title:
                story.append(Paragraph(title, styles["Heading3"]))

            if stype == "key_value":
                data = [
                    [
                        Paragraph(str(p.get("key", "")), label_style),
                        Paragraph(str(p.get("value", "") or ""), value_style),
                    ]
                    for p in (section.get("pairs") or [])
                ]
                if data:
                    t = Table(data, colWidths=[5.5 * cm, None])
                    t.setStyle(TableStyle([
                        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
                        ("BACKGROUND", (0, 0), (0, -1),  colors.HexColor("#f5f5f5")),
                        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING",    (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                    ]))
                    story.append(t)

            elif stype == "table":
                columns = section.get("columns") or []
                rows = section.get("rows") or []
                if columns:
                    header = [Paragraph(f"<b>{c}</b>", value_style) for c in columns]
                    body = [
                        [Paragraph(str(v or ""), value_style) for v in row[:len(columns)]]
                        for row in rows
                    ]
                    t = Table([header] + body)
                    t.setStyle(TableStyle([
                        ("GRID",       (0, 0), (-1, -1), 0.5, colors.black),
                        ("BACKGROUND", (0, 0), (-1, 0),  colors.HexColor("#e0e0e0")),
                        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING",    (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                    ]))
                    story.append(t)

            elif stype == "qa_pair":
                for item in (section.get("items") or []):
                    story.append(Paragraph(str(item.get("question", "")), question_style))
                    answer = str(item.get("answer", "") or "")
                    story.append(Paragraph(answer.replace("\n", "<br/>"), answer_style))
                    story.append(Spacer(1, 0.3 * cm))

            elif stype == "paragraph":
                text = str(section.get("text", "") or "")
                for block in text.split("\n\n"):
                    if block.strip():
                        story.append(Paragraph(block.replace("\n", "<br/>"), value_style))
                        story.append(Spacer(1, 0.2 * cm))

            story.append(Spacer(1, 0.4 * cm))

        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
        story.append(Spacer(1, 0.6 * cm))

    doc.build(story)
    return buf.getvalue()
