from __future__ import annotations

import logging
from pathlib import Path

from contract_audit_rag.config import Settings
from contract_audit_rag.indexing import IndexStore
from contract_audit_rag.ingestion.chunking import chunk_sections
from contract_audit_rag.ingestion.parsers import parse_document
from contract_audit_rag.manifest import Manifest
from contract_audit_rag.models import DocumentRecord, ParseStatus

logger = logging.getLogger(__name__)


class IngestionPipeline:
    def __init__(self, settings: Settings, manifest: Manifest, store: IndexStore) -> None:
        self.settings = settings
        self.manifest = manifest
        self.store = store

    def ingest(self, records: list[DocumentRecord] | None = None) -> dict[str, int]:
        candidates = records if records is not None else self.manifest.all()
        totals = {"documents": 0, "chunks": 0, "needs_ocr": 0, "failed": 0}
        seen_hashes: set[str] = set()
        for record in candidates:
            if record.content_hash in seen_hashes:
                self.manifest.update_status(
                    record.document_id, ParseStatus.SKIPPED, "duplicate content hash"
                )
                continue
            seen_hashes.add(record.content_hash)
            try:
                sections = parse_document(
                    Path(record.local_path), record.content_type, record.document_id
                )
                if not sections and record.content_type == "application/pdf":
                    self.manifest.update_status(record.document_id, ParseStatus.NEEDS_OCR)
                    totals["needs_ocr"] += 1
                    continue
                nodes = chunk_sections(
                    record,
                    sections,
                    self.settings.chunk_size,
                    self.settings.chunk_overlap,
                )
                self.store.delete_document(record.document_id)
                totals["chunks"] += self.store.index(nodes)
                totals["documents"] += 1
                self.manifest.update_status(record.document_id, ParseStatus.INDEXED)
            except Exception as exc:
                logger.exception("Failed to ingest %s", record.canonical_url)
                self.manifest.update_status(record.document_id, ParseStatus.FAILED, str(exc))
                totals["failed"] += 1
        return totals
