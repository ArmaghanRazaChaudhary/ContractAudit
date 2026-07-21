from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class SourcePolicy(BaseModel):
    id: str
    publisher: str
    seeds: list[HttpUrl]
    allowed_domains: list[str]
    allowed_path_prefixes: list[str] = Field(default_factory=lambda: ["/"])
    content_types: list[str] = Field(
        default_factory=lambda: ["text/html", "application/pdf"]
    )
    license: str
    storage_approved: bool = False
    crawl_delay_seconds: float = Field(default=2.0, ge=0.5)
    max_depth: int = Field(default=1, ge=0, le=5)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CAR_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    sources_file: Path = Path("config/sources.yaml")
    qdrant_url: str | None = None
    qdrant_path: Path = Path("data/qdrant")
    collection: str = "evm_security"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_device: str = "cpu"
    chunk_size: int = 700
    chunk_overlap: int = 100
    request_timeout: float = 30.0
    user_agent: str = "ContractAuditRAG/0.1 (local research crawler)"
    max_document_bytes: int = 25_000_000
    mcp_transport: str = "stdio"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8765

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def manifest_path(self) -> Path:
        return self.data_dir / "manifest.sqlite3"

    def prepare_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        if not self.qdrant_url:
            self.qdrant_path.mkdir(parents=True, exist_ok=True)


def load_source_policies(path: Path) -> list[SourcePolicy]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [SourcePolicy.model_validate(item) for item in payload.get("sources", [])]
