"""Infrastructure: HTML snapshotter – fetches pages and extracts text."""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md  # type: ignore[import-untyped]

from research_toolkit.application.ports import Snapshotter as SnapPort


class HtmlSnapshotter(SnapPort):
    """Fetch a URL, return (extracted_markdown, raw_html)."""

    TIMEOUT = 15
    MAX_SIZE = 5_000_000  # 5 MB cap to avoid huge pages

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; ResearchToolkit/0.1; "
            "+https://github.com/research-toolkit)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def capture(self, url: str) -> tuple[str | None, str | None]:
        try:
            with httpx.Client(follow_redirects=True, timeout=self.TIMEOUT) as client:
                resp = client.get(url, headers=self.HEADERS)
                resp.raise_for_status()

            raw_text = resp.text[: self.MAX_SIZE]
            content_type = resp.headers.get("content-type", "")

            # If the response is plain text or markdown, use it directly
            if "text/plain" in content_type or "text/markdown" in content_type:
                clean = raw_text.strip()
                return (clean if clean else None), raw_text

            # If URL looks like a raw markdown file, treat as plain text
            if url.endswith((".md", ".txt", ".rst")) and "<html" not in raw_text[:500].lower():
                clean = raw_text.strip()
                return (clean if clean else None), raw_text

            # Standard HTML processing
            soup = BeautifulSoup(raw_text, "html.parser")

            # Remove noise elements
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
                tag.decompose()

            # Try to find article / main content
            main = soup.find("article") or soup.find("main") or soup.find("body") or soup
            text_md: str = md(str(main), strip=["img"])  # type: ignore[arg-type]

            # Clean up excessive whitespace
            lines = [line.strip() for line in text_md.splitlines()]
            clean = "\n".join(line for line in lines if line)

            return clean if clean.strip() else None, raw_text

        except Exception:
            return None, None
