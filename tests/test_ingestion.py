from __future__ import annotations

from pathlib import Path

from contract_audit_rag.ingestion.chunking import chunk_sections
from contract_audit_rag.ingestion.parsers import parse_html
from contract_audit_rag.models import DocumentRecord


def test_html_sections_preserve_finding_metadata(tmp_path: Path) -> None:
    report = tmp_path / "report.html"
    report.write_text(
        """
        <html><head><title>Example Audit</title></head><body><main>
        <h1>Audit Report</h1><p>Scope and overview.</p>
        <h2>H-01: Reentrancy in withdraw</h2>
        <p>The state update happens after an external call.</p>
        <p>Move the state update before the call.</p>
        </main></body></html>
        """,
        encoding="utf-8",
    )
    sections = parse_html(report, "doc-1")
    finding = next(section for section in sections if section.finding.finding_title)
    assert finding.finding.severity == "high"
    assert finding.finding.finding_title == "Reentrancy in withdraw"


def test_chunk_ids_are_deterministic_and_provenance_is_kept(tmp_path: Path) -> None:
    report = tmp_path / "report.html"
    report.write_text(
        "<main><h2>M-02: Oracle freshness</h2><p>Validate timestamp freshness.</p></main>",
        encoding="utf-8",
    )
    sections = parse_html(report, "doc-1")
    record = DocumentRecord(
        document_id="doc-1",
        source_id="test",
        publisher="Auditor",
        canonical_url="https://example.com/audit",
        content_hash="hash",
        content_type="text/html",
        license="test",
        local_path=str(report),
        title="Audit",
    )
    first = chunk_sections(record, sections, 128, 20)
    second = chunk_sections(record, sections, 128, 20)
    assert [node.node_id for node in first] == [node.node_id for node in second]
    assert first[0].metadata["source_url"] == "https://example.com/audit"
    assert first[0].metadata["severity"] == "medium"
