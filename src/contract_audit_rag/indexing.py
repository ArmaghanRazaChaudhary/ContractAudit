from __future__ import annotations

from functools import cached_property

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import BaseNode
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

from contract_audit_rag.config import Settings


class IndexStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def client(self) -> QdrantClient:
        if self.settings.qdrant_url:
            return QdrantClient(url=self.settings.qdrant_url)
        return QdrantClient(path=str(self.settings.qdrant_path))

    @cached_property
    def embedding(self) -> HuggingFaceEmbedding:
        return HuggingFaceEmbedding(
            model_name=self.settings.embedding_model,
            device=self.settings.embedding_device,
            trust_remote_code=False,
        )

    @cached_property
    def vector_store(self) -> QdrantVectorStore:
        return QdrantVectorStore(
            client=self.client,
            collection_name=self.settings.collection,
            enable_hybrid=True,
            fastembed_sparse_model="Qdrant/bm25",
            batch_size=32,
        )

    def index(self, nodes: list[BaseNode]) -> int:
        if not nodes:
            return 0
        storage = StorageContext.from_defaults(vector_store=self.vector_store)
        VectorStoreIndex(
            nodes=nodes,
            storage_context=storage,
            embed_model=self.embedding,
            show_progress=True,
        )
        return len(nodes)

    def as_index(self) -> VectorStoreIndex:
        return VectorStoreIndex.from_vector_store(
            vector_store=self.vector_store,
            embed_model=self.embedding,
        )

    def delete_document(self, document_id: str) -> None:
        if not self.client.collection_exists(self.settings.collection):
            return
        self.client.delete(
            collection_name=self.settings.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="audit_document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
            wait=True,
        )

    def count(self) -> int:
        if not self.client.collection_exists(self.settings.collection):
            return 0
        return int(self.client.count(self.settings.collection, exact=True).count)

    def close(self) -> None:
        self.client.close()
