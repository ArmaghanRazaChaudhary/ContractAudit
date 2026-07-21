from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ParseStatus(StrEnum):
    FETCHED = "fetched"
    PARSED = "parsed"
    INDEXED = "indexed"
    SKIPPED = "skipped"
    FAILED = "failed"
    NEEDS_OCR = "needs_ocr"


class DocumentRecord(BaseModel):
    document_id: str
    source_id: str
    publisher: str
    canonical_url: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str
    content_type: str
    license: str
    local_path: str
    title: str | None = None
    status: ParseStatus = ParseStatus.FETCHED
    error: str | None = None


class FindingMetadata(BaseModel):
    audit_firm: str | None = None
    project: str | None = None
    audit_date: str | None = None
    language: str = "Solidity"
    severity: str | None = None
    finding_title: str | None = None
    affected_component: str | None = None
    recommendation: str | None = None


class ParsedSection(BaseModel):
    document_id: str
    text: str
    title: str | None = None
    page: int | None = None
    section: str | None = None
    finding: FindingMetadata = Field(default_factory=FindingMetadata)


class Evidence(BaseModel):
    chunk_id: str
    document_id: str
    excerpt: str
    title: str | None = None
    publisher: str | None = None
    source_url: str
    page: int | None = None
    section: str | None = None
    severity: str | None = None
    score: float | None = None
