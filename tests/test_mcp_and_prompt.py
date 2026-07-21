from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from contract_audit_rag.llm.base import CallableAdapter, evidence_prompt
from contract_audit_rag.llm.mcp_host import MCPQwenHost
from contract_audit_rag.mcp.server import mcp
from contract_audit_rag.models import Evidence


def test_mcp_exposes_read_only_retrieval_tools() -> None:
    names = set(mcp._tool_manager._tools)  # noqa: SLF001
    assert names == {
        "search_security_knowledge",
        "get_audit_finding",
        "get_document_context",
        "list_sources",
        "corpus_status",
    }


def test_evidence_prompt_marks_context_untrusted_and_cites_sources() -> None:
    prompt = evidence_prompt(
        "Can this withdraw function reenter?",
        [
            Evidence(
                chunk_id="chunk",
                document_id="doc",
                excerpt="External call happens before state update.",
                source_url="https://example.com/report",
            )
        ],
    )
    assert "untrusted data" in prompt
    assert "https://example.com/report" in prompt
    assert "Cite claims as [1]" in prompt


@pytest.mark.asyncio
async def test_mcp_stdio_handshake_and_tool_schemas() -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "contract_audit_rag.mcp.server"],
    )
    async with (
        stdio_client(parameters) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        status = await session.call_tool("corpus_status")
    assert {tool.name for tool in tools.tools} == {
        "search_security_knowledge",
        "get_audit_finding",
        "get_document_context",
        "list_sources",
        "corpus_status",
    }
    assert not status.isError


@pytest.mark.asyncio
async def test_qwen_host_passes_mcp_evidence_to_ask_callable() -> None:
    class FakeSession:
        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            assert name == "search_security_knowledge"
            assert arguments["query"] == "What is the risk?"
            return SimpleNamespace(
                isError=False,
                structuredContent={
                    "result": [
                        {
                            "chunk_id": "chunk",
                            "document_id": "doc",
                            "excerpt": "A stale oracle value can misprice collateral.",
                            "source_url": "https://example.com/audit",
                        }
                    ]
                },
            )

    host = MCPQwenHost(CallableAdapter(lambda prompt: f"Qwen received {len(prompt)} chars"))
    answer, evidence = await host.answer(FakeSession(), "What is the risk?")
    assert answer.startswith("Qwen received")
    assert evidence[0].source_url == "https://example.com/audit"
