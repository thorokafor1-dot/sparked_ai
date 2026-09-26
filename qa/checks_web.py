"""Checks for the landing page: every local link and asset must resolve.

The ToS/privacy/OAuth-callback pages are referenced by live platform app reviews, so a
broken local link there is a real outage, not a cosmetic bug.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from checks import check, read_text

REF_RX = re.compile(r"""(?:href|src)\s*=\s*["']([^"'#?]+)""", re.I)
CSS_URL_RX = re.compile(r"""url\(\s*["']?([^"')#?]+)""", re.I)


@check("landing-local-links", paths=["landing-page/*"], exts={".html", ".css"})
def landing_local_links(path: Path) -> list[str]:
    text = read_text(path) or ""
    # Inline data: URIs (e.g. an SVG noise filter) contain their own url(#id) refs; not files.
    text = re.sub(r"\"data:[^\"]*\"|'data:[^']*'", '""', text)
    refs = REF_RX.findall(text) + CSS_URL_RX.findall(text)
    problems = []
    for ref in refs:
        u = urlparse(ref)
        if u.scheme or ref.startswith(("//", "mailto:", "tel:", "javascript:", "data:")):
            continue
        target = (path.parent / unquote(ref.lstrip("/"))).resolve() if not ref.startswith("/") \
            else (path.parent / unquote(ref.lstrip("/"))).resolve()
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            problems.append(f"broken local link/asset: {ref}")
    if path.suffix == ".html" and "<title>" not in text.lower():
        problems.append("page has no <title>")
    return sorted(set(problems))
