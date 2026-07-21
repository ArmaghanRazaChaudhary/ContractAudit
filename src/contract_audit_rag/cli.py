from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

import typer

from contract_audit_rag.config import Settings, load_source_policies
from contract_audit_rag.evaluation import evaluate
from contract_audit_rag.indexing import IndexStore
from contract_audit_rag.ingestion.crawler import GovernedCrawler
from contract_audit_rag.ingestion.pipeline import IngestionPipeline
from contract_audit_rag.manifest import Manifest
from contract_audit_rag.retrieval.service import RetrievalService

app = typer.Typer(no_args_is_help=True, help="Local EVM contract-audit knowledge system.")
source_app = typer.Typer(no_args_is_help=True)
app.add_typer(source_app, name="sources")


def _settings() -> Settings:
    settings = Settings()
    settings.prepare_directories()
    return settings


def _print(payload: object) -> None:
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


@source_app.command("validate")
def validate_sources() -> None:
    settings = _settings()
    policies = load_source_policies(settings.sources_file)
    _print(
        {
            "valid": True,
            "count": len(policies),
            "sources": [
                {
                    "id": policy.id,
                    "publisher": policy.publisher,
                    "seeds": [str(seed) for seed in policy.seeds],
                    "domains": policy.allowed_domains,
                    "storage_approved": policy.storage_approved,
                }
                for policy in policies
            ],
        }
    )


@app.command()
def crawl(
    source: Annotated[str | None, typer.Option(help="Source ID; defaults to all.")] = None,
    limit: Annotated[int, typer.Option(min=1, max=10000)] = 100,
) -> None:
    settings = _settings()
    manifest = Manifest(settings.manifest_path)
    policies = load_source_policies(settings.sources_file)
    selected = [policy for policy in policies if source is None or policy.id == source]
    if not selected:
        raise typer.BadParameter(f"Unknown source: {source}")
    results: dict[str, int | str] = {}
    with GovernedCrawler(settings, manifest) as crawler:
        for policy in selected:
            if not policy.storage_approved:
                results[policy.id] = "skipped: storage approval required"
                continue
            results[policy.id] = len(crawler.crawl(policy, limit=limit))
    _print(results)


@app.command()
def ingest() -> None:
    settings = _settings()
    manifest = Manifest(settings.manifest_path)
    store = IndexStore(settings)
    try:
        _print(IngestionPipeline(settings, manifest, store).ingest())
    finally:
        store.close()


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Security question or concept.")],
    limit: Annotated[int, typer.Option(min=1, max=50)] = 8,
    publisher: Annotated[str | None, typer.Option()] = None,
    severity: Annotated[str | None, typer.Option()] = None,
    neighbors: Annotated[bool, typer.Option()] = False,
) -> None:
    settings = _settings()
    store = IndexStore(settings)
    try:
        service = RetrievalService(store, Manifest(settings.manifest_path))
        filters = {
            key: value
            for key, value in {"publisher": publisher, "severity": severity}.items()
            if value
        }
        _print(
            [
                item.model_dump(mode="json")
                for item in service.search(
                    query, limit=limit, filters=filters, include_neighbors=neighbors
                )
            ]
        )
    finally:
        store.close()


@app.command()
def inspect(document_id: str, limit: int = 50) -> None:
    settings = _settings()
    store = IndexStore(settings)
    try:
        service = RetrievalService(store, Manifest(settings.manifest_path))
        _print(
            [
                item.model_dump(mode="json")
                for item in service.document_context(document_id, limit)
            ]
        )
    finally:
        store.close()


@app.command()
def stats() -> None:
    settings = _settings()
    store = IndexStore(settings)
    try:
        _print(RetrievalService(store, Manifest(settings.manifest_path)).status())
    finally:
        store.close()


@app.command()
def benchmark(
    path: Annotated[Path, typer.Option()] = Path("eval/evm_queries.yaml"),
    limit: Annotated[int, typer.Option(min=1, max=50)] = 8,
) -> None:
    settings = _settings()
    store = IndexStore(settings)
    try:
        service = RetrievalService(store, Manifest(settings.manifest_path))
        _print(evaluate(service, path, limit))
    finally:
        store.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    app()


if __name__ == "__main__":
    main()
