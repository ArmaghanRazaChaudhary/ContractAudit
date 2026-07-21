from __future__ import annotations

import hashlib

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import BaseNode

from contract_audit_rag.models import DocumentRecord, ParsedSection

CHUNKING_VERSION = "sentence-v1"


def chunk_sections(
    record: DocumentRecord,
    sections: list[ParsedSection],
    chunk_size: int,
    chunk_overlap: int,
) -> list[BaseNode]:
    splitter = SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        include_metadata=True,
        include_prev_next_rel=True,
    )
    documents: list[Document] = []
    for ordinal, section in enumerate(sections):
        metadata = {
            "document_id": record.document_id,
            "audit_document_id": record.document_id,
            "source_id": record.source_id,
            "publisher": record.publisher,
            "source_url": record.canonical_url,
            "license": record.license,
            "document_title": record.title or "",
            "section": section.section or "",
            "page": section.page or 0,
            "severity": section.finding.severity or "",
            "finding_title": section.finding.finding_title or "",
            "language": section.finding.language,
            "content_hash": record.content_hash,
            "chunking_version": CHUNKING_VERSION,
            "section_ordinal": ordinal,
        }
        documents.append(
            Document(
                text=section.text,
                metadata=metadata,
                id_=f"{record.document_id}:section:{ordinal}",
            )
        )
    nodes = splitter.get_nodes_from_documents(documents, show_progress=False)
    for chunk_ordinal, node in enumerate(nodes):
        digest = hashlib.sha256(
            f"{record.document_id}\0{node.get_content()}".encode()
        ).hexdigest()
        node.id_ = digest[:32]
        node.metadata["chunk_hash"] = digest
        node.metadata["chunk_ordinal"] = chunk_ordinal
    return nodes
