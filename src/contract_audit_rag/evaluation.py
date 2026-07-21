from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from contract_audit_rag.retrieval.service import RetrievalService


def evaluate(service: RetrievalService, benchmark_path: Path, limit: int = 8) -> dict[str, Any]:
    payload = yaml.safe_load(benchmark_path.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    for case in payload["queries"]:
        evidence = service.search(case["question"], limit=limit)
        text = " ".join(item.excerpt.lower() for item in evidence)
        expected = [term.lower() for term in case["expected_terms"]]
        matched = [term for term in expected if term in text]
        results.append(
            {
                "id": case["id"],
                "passed": bool(matched),
                "matched_terms": matched,
                "result_count": len(evidence),
            }
        )
    passed = sum(int(result["passed"]) for result in results)
    return {
        "passed": passed,
        "total": len(results),
        "recall_at_k": passed / len(results) if results else 0.0,
        "results": results,
    }
