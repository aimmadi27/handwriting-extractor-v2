from collections import defaultdict
from typing import Any, Dict

# ---------------------------------------------------------------------------
# In-memory stores
# Replace with Redis for multi-worker / production deployments.
# ---------------------------------------------------------------------------

# upload_id -> {filename, page_images: [bytes], total_pages}
pdf_store: Dict[str, dict] = {}

# upload_id -> {page_num (int): result_dict}
result_store: Dict[str, Dict[int, Any]] = defaultdict(dict)

# OAuth state -> {verifier: str, ts: float}
pkce_store: Dict[str, dict] = {}
