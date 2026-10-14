"""Build a self-contained Cloudflare Worker; no origin assets needed during an outage."""

import json
from pathlib import Path

from aedrova_site.error_pages import error_html, error_response

root = Path(__file__).resolve().parents[1]
folder = root / "deploy" / "error-fallback"
folder.mkdir(exist_ok=True)
html = error_html(503)
headers = dict(error_response(503).headers)
headers.pop("content-length", None)
(folder / "fallback.mjs").write_text(
    "export const HTML = "
    + json.dumps(html, ensure_ascii=False)
    + ";\nexport const HEADERS = "
    + json.dumps(headers)
    + ";\n"
)
(root / "work" / "error-preview.html").write_text(html)
