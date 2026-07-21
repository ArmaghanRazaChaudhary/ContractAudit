from __future__ import annotations

from typing import Any

from llama_index.core.schema import BaseNode, NodeRelationship
from llama_index.core.vector_stores import ExactMatchFilter, MetadataFilters
from qdrant_client import models

from contract_audit_rag.indexing import IndexStore
from contract_audit_rag.manifest import Manifest
from contract_audit_rag.models import Evidence


class RetrievalService:
    def __init__(self, store: IndexStore, manifest: Manifest) -> None:
        self.store = store
        self.manifest = manifest

    @staticmethod
    def _evidence(node: BaseNode, score: float | None = None) -> Evidence:
        metadata = node.metadata
        page = int(metadata.get("page", 0)) or None
        return Evidence(
            chunk_id=node.node_id,
            document_id=str(metadata.get("audit_document_id") or metadata["document_id"]),
            excerpt=node.get_content(),
            title=metadata.get("document_title") or metadata.get("finding_title") or None,
            publisher=metadata.get("publisher") or None,
            source_url=str(metadata["source_url"]),
            page=page,
            section=metadata.get("section") or None,
            severity=metadata.get("severity") or None,
            score=score,
        )

    def search(
        self,
        query: str,
        limit: int = 8,
        filters: dict[str, str] | None = None,
        min_score: float | None = None,
        include_neighbors: bool = False,
    ) -> list[Evidence]:
        metadata_filters = None
        if filters:
            metadata_filters = MetadataFilters(
                filters=[
                    ExactMatchFilter(key=key, value=value)
                    for key, value in filters.items()
                    if value
                ]
            )
        retriever = self.store.as_index().as_retriever(
            vector_store_query_mode="hybrid",
            similarity_top_k=limit,
            sparse_top_k=max(limit, 12),
            alpha=0.5,
            filters=metadata_filters,
        )
        results = retriever.retrieve(query)
        evidence: list[Evidence] = []
        seen: set[str] = set()
        for result in results:
            if min_score is not None and (result.score or 0.0) < min_score:
                continue
            evidence.append(self._evidence(result.node, result.score))
            seen.add(result.node.node_id)
            if include_neighbors:
                for neighbor in self._neighbors(result.node):
                    if neighbor.node_id not in seen:
                        evidence.append(self._evidence(neighbor))
                        seen.add(neighbor.node_id)
        return evidence

    def _neighbors(self, node: BaseNode) -> list[BaseNode]:
        ids: list[str] = []
        for relation in (NodeRelationship.PREVIOUS, NodeRelationship.NEXT):
            related = node.relationships.get(relation)
            if isinstance(related, list):
                ids.extend(item.node_id for item in related)
            elif related is not None:
                ids.append(related.node_id)
        return self.store.vector_store.get_nodes(node_ids=ids) if ids else []

    def get_chunk(self, chunk_id: str) -> Evidence | None:
        nodes = self.store.vector_store.get_nodes(node_ids=[chunk_id])
        return self._evidence(nodes[0]) if nodes else None

    def document_context(self, document_id: str, limit: int = 50) -> list[Evidence]:
        points, _ = self.store.client.scroll(
            collection_name=self.store.settings.collection,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="audit_document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            ),
            limit=limit,
            with_payload=False,
            with_vectors=False,
        )
        nodes = self.store.vector_store.get_nodes(node_ids=[str(point.id) for point in points])
        nodes.sort(key=lambda node: int(node.metadata.get("chunk_ordinal", 0)))
        return [self._evidence(node) for node in nodes]

    def sources(self) -> list[dict[str, Any]]:
        return [
            {
                "document_id": record.document_id,
                "publisher": record.publisher,
                "title": record.title,
                "url": record.canonical_url,
                "license": record.license,
                "status": record.status.value,
            }
            for record in self.manifest.all()
        ]

    def status(self) -> dict[str, Any]:
        return {
            "collection": self.store.settings.collection,
            "chunks": self.store.count(),
            "documents_by_status": self.manifest.counts(),
            "embedding_model": self.store.settings.embedding_model,
        }
