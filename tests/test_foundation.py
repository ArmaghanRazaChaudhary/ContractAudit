from __future__ import annotations

from pathlib import Path

from contract_audit_rag.config import load_source_policies
from contract_audit_rag.ingestion.crawler import canonicalize_url, url_allowed
from contract_audit_rag.manifest import Manifest
from contract_audit_rag.models import DocumentRecord, ParseStatus


def test_source_configuration_is_valid() -> None:
    policies = load_source_policies(Path("config/sources.yaml"))
    assert {policy.id for policy in policies} >= {
        "solidity_docs",
        "openzeppelin_audits",
        "trailofbits_secure_contracts",
    }
    assert all(policy.crawl_delay_seconds >= 0.5 for policy in policies)


def test_url_policy_rejects_other_domains_and_paths() -> None:
    policy = load_source_policies(Path("config/sources.yaml"))[0]
    assert url_allowed(
        "https://docs.soliditylang.org/en/latest/security-considerations.html", policy
    )
    assert not url_allowed("https://example.com/en/latest/security-considerations.html", policy)
    assert not url_allowed("https://docs.soliditylang.org/projects/private", policy)
    assert canonicalize_url("HTTPS://EXAMPLE.COM/report#finding") == "https://example.com/report"


def test_manifest_upsert_and_status_are_idempotent(tmp_path: Path) -> None:
    manifest = Manifest(tmp_path / "manifest.sqlite3")
    record = DocumentRecord(
        document_id="doc-1",
        source_id="test",
        publisher="Auditor",
        canonical_url="https://example.com/report",
        content_hash="abc",
        content_type="text/html",
        license="test-license",
        local_path="report.html",
    )
    manifest.upsert(record)
    manifest.upsert(record)
    manifest.update_status(record.document_id, ParseStatus.INDEXED)
    assert len(manifest.all()) == 1
    assert manifest.get("doc-1").status == ParseStatus.INDEXED  # type: ignore[union-attr]
