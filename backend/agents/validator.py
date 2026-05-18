import json
import time

from logger import get_logger

log = get_logger(__name__)

# Split into two parts so no template substitution is needed at all.
# The extracted JSON is inserted between them via plain concatenation.

_PROMPT_HEAD = """You are a document quality validator.

Below is a structured document extracted from a handwritten page.
Review it and return a corrected version with confidence scores.

EXTRACTED DOCUMENT:
"""

_PROMPT_TAIL = """

Your tasks:
1. Check every extracted value for obvious errors:
   - Malformed dates, invalid phone numbers, wrong number formats
   - Values that clearly don't match their field label
   - Truncated or incomplete answers
2. Assign a confidence score (0.0-1.0) to each section:
   - 1.0       -> clearly correct and complete
   - 0.7-0.9   -> likely correct, minor uncertainty
   - 0.4-0.6   -> uncertain, possible misread
   - 0.0-0.3   -> likely wrong, illegible, or incomplete
3. Correct ONLY obvious errors where you are confident.
4. Do NOT change values you are uncertain about, flag them in section_issues instead.
5. Compute overall_confidence as the average of all section confidence scores.

Return STRICTLY valid JSON with exactly this structure:
- Top-level key "document" containing the corrected document (same structure as input)
- Top-level key "validation" containing:
    - "overall_confidence": number between 0.0 and 1.0
    - "section_issues": array of objects, each with:
        - "section_index": integer index of the affected section
        - "issue": string describing the problem
        - "confidence": number between 0.0 and 1.0

If there are no issues, section_issues must be an empty array.
No extra text. No comments. Valid JSON only.
"""


class ValidatorAgent:
    def __init__(self, llm):
        self.llm = llm

    def validate(self, parsed: dict, page_num: int) -> dict:
        """Validate the parsed document structure and return corrected doc + issue report."""
        log.info("validating page=%d", page_num)

        doc_clean = {k: v for k, v in parsed.items() if not k.startswith("_")}
        prompt = _PROMPT_HEAD + json.dumps(doc_clean, indent=2) + _PROMPT_TAIL

        for attempt in range(3):
            try:
                result, usage = self.llm.generate_json(prompt)
                if "document" not in result:
                    result = {
                        "document": doc_clean,
                        "validation": {"overall_confidence": 1.0, "section_issues": []},
                    }
                result["_usage"] = usage
                return result
            except Exception as e:
                log.warning("validator attempt=%d page=%d error=%s", attempt + 1, page_num, e)
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    return {
                        "document": doc_clean,
                        "_usage": {},
                        "validation": {
                            "overall_confidence": 0.0,
                            "section_issues": [{
                                "section_index": -1,
                                "issue": f"Validation failed: {e}",
                                "confidence": 0.0,
                            }],
                        },
                    }
