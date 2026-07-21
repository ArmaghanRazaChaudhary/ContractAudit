from __future__ import annotations

import json
from typing import Any, Protocol

from contract_audit_rag.llm.base import LLMAdapter, evidence_prompt
from contract_audit_rag.models import Evidence


class MCPToolSession(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool on a connected MCP session."""
        ...


class MCPQwenHost:
    """Connects a Qwen-compatible ask() adapter to the retrieval MCP."""

    def __init__(self, adapter: LLMAdapter) -> None:
        self.adapter = adapter

    async def answer(
        self,
        session: MCPToolSession,
        question: str,
        limit: int = 8,
    ) -> tuple[str, list[Evidence]]:
        result = await session.call_tool(
            "search_security_knowledge",
            {"query": question, "limit": min(max(limit, 1), 20)},
        )
        if getattr(result, "isError", False):
            raise RuntimeError("MCP retrieval tool returned an error")
        payload = getattr(result, "structuredContent", None)
        if isinstance(payload, dict):
            raw_evidence = payload.get("result", payload.get("evidence", []))
        else:
            text_parts = [
                item.text for item in getattr(result, "content", []) if hasattr(item, "text")
            ]
            raw_evidence = json.loads("".join(text_parts) or "[]")
        if not isinstance(raw_evidence, list):
            raise RuntimeError("MCP retrieval returned an invalid evidence payload")
        evidence = [Evidence.model_validate(item) for item in raw_evidence]
        return self.adapter.ask(evidence_prompt(question, evidence)), evidence
