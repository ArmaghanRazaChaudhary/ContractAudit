from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader

from contract_audit_rag.models import FindingMetadata, ParsedSection

SEVERITY_PATTERN = re.compile(
    r"\b(critical|high|medium|moderate|low|informational|info|note)\b", re.IGNORECASE
)
FINDING_HEADING = re.compile(
    r"^(?:[A-Z]{1,3}[- ]?\d{1,3}|\d+(?:\.\d+)*)[\s:.-]+(.+)$"
)
SEVERITY_PREFIX = re.compile(r"^(C|H|M|L|I)[- ]?\d+", re.IGNORECASE)
PREFIX_SEVERITY = {
    "C": "critical",
    "H": "high",
    "M": "medium",
    "L": "low",
    "I": "informational",
}


def _finding_metadata(heading: str | None) -> FindingMetadata:
    if not heading:
        return FindingMetadata()
    severity_match = SEVERITY_PATTERN.search(heading)
    prefix_match = SEVERITY_PREFIX.match(heading.strip())
    finding_match = FINDING_HEADING.match(heading.strip())
    return FindingMetadata(
        severity=(
            severity_match.group(1).lower()
            if severity_match
            else PREFIX_SEVERITY.get(prefix_match.group(1).upper()) if prefix_match else None
        ),
        finding_title=finding_match.group(1).strip() if finding_match else None,
    )


def parse_html(path: Path, document_id: str) -> list[ParsedSection]:
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    for element in soup.select("script, style, nav, footer, noscript, svg"):
        element.decompose()
    root = soup.select_one("main, article, [role=main]") or soup.body or soup
    sections: list[ParsedSection] = []
    heading: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        text = "\n\n".join(buffer).strip()
        if text:
            sections.append(
                ParsedSection(
                    document_id=document_id,
                    text=text,
                    title=heading,
                    section=heading,
                    finding=_finding_metadata(heading),
                )
            )
        buffer.clear()

    for element in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "pre", "code"]):
        text = element.get_text(" ", strip=True)
        if not text:
            continue
        if element.name in {"h1", "h2", "h3", "h4"}:
            flush()
            heading = text
        elif not element.find_parent(["p", "li", "pre", "code"]):
            buffer.append(text)
    flush()
    return sections


def parse_pdf(path: Path, document_id: str) -> list[ParsedSection]:
    reader = PdfReader(path)
    sections: list[ParsedSection] = []
    total_characters = 0
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        total_characters += len(text)
        if text:
            first_line = text.splitlines()[0][:200]
            sections.append(
                ParsedSection(
                    document_id=document_id,
                    text=text,
                    title=first_line,
                    page=page_number,
                    section=first_line,
                    finding=_finding_metadata(first_line),
                )
            )
    if reader.pages and total_characters / len(reader.pages) < 40:
        return []
    return sections


def parse_document(path: Path, content_type: str, document_id: str) -> list[ParsedSection]:
    if content_type == "application/pdf":
        return parse_pdf(path, document_id)
    if content_type == "text/html":
        return parse_html(path, document_id)
    raise ValueError(f"Unsupported content type: {content_type}")
