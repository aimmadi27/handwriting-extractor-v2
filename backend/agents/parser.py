import time

from logger import get_logger

log = get_logger(__name__)

PARSER_PROMPT = """
You are an expert document parser and OCR assistant.
You will receive an image of a handwritten or filled document page.

TASK:
1. Identify the document type.
2. Extract ALL visible content from the page into a structured JSON document.

DOCUMENT TYPES — choose the closest match:
  form        → structured fields with printed labels and handwritten values
  receipt     → purchase or transaction record with items and totals
  letter      → addressed correspondence with body text
  assessment  → exam, test, or homework with questions and written answers
  bank_slip   → deposit, withdrawal, or transfer record
  invoice     → billing document with line items
  notes       → free-form handwritten notes or a journal
  other       → anything not covered above

────────────────────────────────────────────────────────────
SECTION TYPES — break the document into sections using these:
────────────────────────────────────────────────────────────

"key_value" → labeled fields and their handwritten values
{
  "type": "key_value",
  "title": "section heading or null",
  "pairs": [
    {"key": "printed label text", "value": "handwritten value or null"}
  ]
}

"table" → rows and columns of data
{
  "type": "table",
  "title": "table heading or null",
  "columns": ["Column Header 1", "Column Header 2"],
  "rows": [
    ["cell value", "cell value or null"]
  ]
}

"qa_pair" → question-answer pairs (exams, surveys, interviews)
{
  "type": "qa_pair",
  "title": "section heading or null",
  "items": [
    {
      "question": "Full printed question text",
      "answer": "Complete handwritten answer text or null"
    }
  ]
}

"paragraph" → continuous prose text (letters, notes, descriptions)
{
  "type": "paragraph",
  "title": "paragraph heading or null",
  "text": "Full paragraph text. Use \\n\\n for paragraph breaks."
}

────────────────────────────────────────────────────────────
CRITICAL RULES:
────────────────────────────────────────────────────────────
1. Cover the ENTIRE page — do not skip any content.
2. Extract ONLY handwritten or user-filled values — not printed instructions or decorative text.
3. For qa_pair: capture the COMPLETE handwritten answer in one field. Never split it by line.
4. For paragraph: capture the full block of text. Never create one section per sentence or line.
5. For key_value: never create one pair per word — one pair per labeled field.
6. Aim for 2–8 sections per page. A document should NOT have one section per line.
7. Choose section type from the content structure, not the document type.
8. A single page can mix section types (e.g., receipt = key_value + table + key_value).
9. Missing, blank, or illegible content → null (never guess).
10. Dates → YYYY-MM-DD if clearly readable. Phone → E.164 if clearly readable.

Return ONLY valid JSON with this structure — no extra text, no comments:
{
  "doc_type": "form|receipt|letter|assessment|bank_slip|invoice|notes|other",
  "title": "Short descriptive title for this page",
  "sections": [ ...section objects... ]
}
"""


class ParserAgent:
    def __init__(self, llm):
        self.llm = llm

    def parse(self, image_bytes: bytes, page_num: int) -> dict:
        """
        Classify the document type and extract its full content
        as a structured section list in a single LLM call.
        """
        log.info("parsing page=%d", page_num)

        for attempt in range(3):
            try:
                result, usage = self.llm.generate_json(PARSER_PROMPT, image_bytes)
                result["_page"]  = page_num
                result["_usage"] = usage
                return result
            except Exception as e:
                log.warning("parser attempt=%d page=%d error=%s", attempt + 1, page_num, e)
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    return {
                        "doc_type": "other",
                        "title": f"Page {page_num}",
                        "sections": [],
                        "_page":  page_num,
                        "_usage": {},
                        "_error": str(e),
                    }
