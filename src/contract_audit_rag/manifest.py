from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from contract_audit_rag.models import DocumentRecord, ParseStatus


class Manifest:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    publisher TEXT NOT NULL,
                    canonical_url TEXT NOT NULL UNIQUE,
                    retrieved_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    license TEXT NOT NULL,
                    local_path TEXT NOT NULL,
                    title TEXT,
                    status TEXT NOT NULL,
                    error TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash)"
            )

    def upsert(self, record: DocumentRecord) -> None:
        values = record.model_dump(mode="json")
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO documents (
                    document_id, source_id, publisher, canonical_url, retrieved_at,
                    content_hash, content_type, license, local_path, title, status, error
                ) VALUES (
                    :document_id, :source_id, :publisher, :canonical_url, :retrieved_at,
                    :content_hash, :content_type, :license, :local_path, :title, :status, :error
                )
                ON CONFLICT(canonical_url) DO UPDATE SET
                    document_id=excluded.document_id,
                    retrieved_at=excluded.retrieved_at,
                    content_hash=excluded.content_hash,
                    content_type=excluded.content_type,
                    local_path=excluded.local_path,
                    title=excluded.title,
                    status=excluded.status,
                    error=excluded.error
                """,
                values,
            )

    def update_status(
        self, document_id: str, status: ParseStatus, error: str | None = None
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE documents SET status = ?, error = ? WHERE document_id = ?",
                (status.value, error, document_id),
            )

    def get(self, document_id: str) -> DocumentRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE document_id = ?", (document_id,)
            ).fetchone()
        return DocumentRecord.model_validate(dict(row)) if row else None

    def all(self, status: ParseStatus | None = None) -> list[DocumentRecord]:
        query = "SELECT * FROM documents"
        parameters: tuple[str, ...] = ()
        if status:
            query += " WHERE status = ?"
            parameters = (status.value,)
        query += " ORDER BY retrieved_at DESC"
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [DocumentRecord.model_validate(dict(row)) for row in rows]

    def counts(self) -> dict[str, int]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM documents GROUP BY status"
            ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}
