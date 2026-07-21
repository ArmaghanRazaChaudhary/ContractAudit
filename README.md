# ContractAudit RAG

### Local-first retrieval for EVM smart-contract security knowledge — crawl, index, cite.

**ContractAudit** is an audit **research assistant**: it crawls an explicit source allowlist, extracts HTML/PDF, builds provenance-preserving chunks (LlamaIndex), stores hybrid dense + BM25 vectors in **Qdrant**, and exposes read-only search through **MCP**.

It helps you find *what auditors and docs already said* about a class of bugs. It is **not** a certificate that any contract is safe.

```text
approved sources → governed crawler → parsers → LlamaIndex chunks
        → Qdrant (hybrid) → retrieval service → MCP tools → (optional) local LLM host
```

---

## What it does

| Capability | Details |
|------------|---------|
| **Governed crawling** | Domain / path allowlists, crawl delay, size caps, `storage_approved` gate |
| **Ingestion** | HTML + PDF extraction, chunking with stable IDs + provenance |
| **Hybrid search** | Dense embeddings (`BAAI/bge-small-en-v1.5`) + sparse/BM25 via Qdrant |
| **MCP server** | Read-only tools for IDE / agent hosts (`stdio` or local HTTP) |
| **Eval harness** | Starter benchmark queries in `eval/evm_queries.yaml` |
| **LLM seam** | Optional host retrieves evidence via MCP, then calls your local `ask()` |

**MCP tools:** `search_security_knowledge` · `get_audit_finding` · `get_document_context` · `list_sources` · `corpus_status`

Crawling and indexing stay **operator-controlled CLI** actions so prompt content cannot mutate the corpus.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Language | Python **3.11+**, packaged with Hatchling |
| CLI | **Typer** (`contract-audit-rag`, `contract-audit-mcp`) |
| Config | **Pydantic Settings**, YAML source policies |
| Crawl / parse | **httpx**, BeautifulSoup, **trafilatura**, **pypdf** |
| Chunking / RAG | **LlamaIndex** + HuggingFace embeddings |
| Vector DB | **Qdrant** (embedded path or server URL) |
| Sparse vectors | **fastembed** |
| Agent interface | **MCP** (`mcp[cli]`) — stdio / streamable-HTTP |
| Quality | **pytest**, **ruff**, **mypy** (strict) |

Optional: OCR extras (`pymupdf`, `pytesseract`) · docs PDF builder (`reportlab`).

---

## Privacy & repo hygiene

| Included | Excluded (local only) |
|----------|------------------------|
| Source code, tests, `config/sources.yaml` | `.env` |
| `.env.example`, eval queries, docs | `.venv/`, caches |
| Learning guide (md/pdf) | `data/raw/`, `data/qdrant/`, `data/manifest.sqlite3` |

No API keys are required for the default local embedding path. Do not commit crawled corpora or vector stores.

---

## Quick start (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

First search/ingest downloads embedding models. Default dense model runs on **CPU**; set `CAR_EMBEDDING_DEVICE=cuda` only if VRAM allows.

Embedded Qdrant (`data/qdrant`) allows **one** process at a time. For concurrent ingest + MCP, run Qdrant as a service and set `CAR_QDRANT_URL=http://localhost:6333`.

### Build a small corpus

Review `config/sources.yaml` first (robots, terms, report licenses).

```powershell
contract-audit-rag sources validate
contract-audit-rag crawl --source trailofbits_secure_contracts --limit 30
contract-audit-rag ingest
contract-audit-rag stats
contract-audit-rag search "How should oracle price freshness be checked?"
contract-audit-rag benchmark
```

### MCP

```powershell
contract-audit-mcp
```

For a local network client: `CAR_MCP_TRANSPORT=streamable-http` (default `127.0.0.1:8765`). Do not expose publicly without auth/TLS.

### Tests

```powershell
ruff check .
mypy src
pytest
```

---

## Optional local-model phase

Wire any local model callable through `contract_audit_rag.llm.base.CallableAdapter`, then use `MCPQwenHost.answer()` with a connected MCP `ClientSession`. The host:

1. Calls `search_security_knowledge`
2. Validates structured evidence
3. Builds an `evidence_prompt` (untrusted web content, required citations, insufficient-evidence path)

The raw model is **not** an MCP client — the application host owns tool calls.

---

## Repo map

```text
ContractAudit/
├── config/sources.yaml          # Crawl allowlist (review before use)
├── src/contract_audit_rag/
│   ├── cli.py                   # Typer CLI
│   ├── ingestion/               # Crawler, parsers, pipeline, chunking
│   ├── retrieval/               # Search service
│   ├── indexing.py              # Qdrant index store
│   ├── mcp/server.py            # MCP tools
│   └── llm/                     # Optional host + adapter seam
├── eval/evm_queries.yaml
├── tests/
├── docs/                        # Learning guide (md + pdf)
├── tools/build_learning_guide.py
├── .env.example
└── pyproject.toml
```

---

## Design notes

- **Allowlist-first security posture** for anything that hits the network.
- **Provenance-preserving chunks** so answers can be cited, not hand-waved.
- **Read-only MCP surface** — corpus mutation is never a tool side effect.
- **Hybrid retrieval** for both semantic and keyword-heavy audit jargon.
- **Honest product boundary:** research assistant ≠ automated audit sign-off.

---

## Learning guide

Detailed walkthrough: [`docs/Contract_Audit_RAG_Learning_Guide.pdf`](docs/Contract_Audit_RAG_Learning_Guide.pdf) (Markdown source alongside).

```powershell
python -m pip install -e ".[docs]"
python tools\build_learning_guide.py
```

---

## License

MIT — see [LICENSE](LICENSE). Respect third-party content licenses when crawling or redistributing reports.
