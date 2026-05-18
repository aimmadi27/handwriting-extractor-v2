from copy import deepcopy
from agents.parser import ParserAgent
from agents.validator import ValidatorAgent


class Orchestrator:
    """
    Coordinates the two-agent pipeline for each page:
      1. ParserAgent    → classifies doc type + extracts full document structure
      2. ValidatorAgent → validates, corrects, and scores the extracted structure
    """

    def __init__(self, llm):
        self.parser = ParserAgent(llm)
        self.validator = ValidatorAgent(llm)

    def run_page(self, image_bytes: bytes, page_num: int, progress_cb=None) -> dict:
        """
        Run the full pipeline on a single page.

        Returns:
            {
                "doc_type":   str,
                "title":      str,
                "sections":   list,          # validated + corrected
                "validation": dict           # confidence scores + issues
            }
        """
        if progress_cb:
            progress_cb(page_num, "parsing")
        parsed = self.parser.parse(image_bytes, page_num)

        if progress_cb:
            progress_cb(page_num, "validating")
        validated = self.validator.validate(parsed, page_num)

        document = validated.get("document", parsed)
        document["_page"] = page_num

        return {
            "doc_type":   document.get("doc_type", "other"),
            "title":      document.get("title", f"Page {page_num}"),
            "sections":   document.get("sections", []),
            "validation": validated.get("validation", {"overall_confidence": 1.0, "section_issues": []}),
        }

    def run(self, pages: list[bytes], page_nums: list[int], progress_cb=None) -> dict:
        """
        Run the pipeline on all pages.

        Returns dict keyed by page_num, each value is the result of run_page().
        """
        results = {}
        for image_bytes, page_num in zip(pages, page_nums):
            results[page_num] = self.run_page(image_bytes, page_num, progress_cb)
        return results
