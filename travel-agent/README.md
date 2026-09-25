# Travel Agent Platform Skeleton

This repository is a production-oriented Python agent runtime skeleton. It deliberately contains no travel-product logic. Spring Boot remains the business backend; Python owns agent orchestration, model and tool abstractions, and integration adapters.

## Runtime architecture

```text
Spring Boot
    │ HTTP / future MCP
    ▼
HMDP Integration Layer
    │ domain adaptation
    ▼
Agent Service → Agent Runtime → LangGraph
                              ├── LLM abstraction
                              └── Tool registry/executor
```

Java's `success`, `errorMsg`, `data`, and `total` envelope is parsed only inside `app/integrations/hmdp`. Agent code receives provider-independent domain models.

## Requirements

- Python 3.11+
- conda-provided Python is supported and used by the local project
- [uv](https://docs.astral.sh/uv/)

No LLM key or running Java service is required for local startup or tests. The default `fake` model is deterministic. A real OpenAI-compatible Chat Completions provider can be enabled entirely through configuration.

## Local setup

```powershell
Copy-Item .env.example .env
uv sync
uv run pytest
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The service exposes:

- `GET /health` — confirms that the process is serving requests.
- `GET /ready` — confirms that currently required in-process components initialized.
- `POST /api/v1/agent/run` — executes the minimal generic LangGraph workflow.

Example request:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/agent/run `
  -ContentType application/json `
  -Body '{"prompt":"platform check","conversation_id":"demo"}'
```

Request correlation headers are optional: `x-request-id`, `x-conversation-id`, and `x-user-id`. The server generates missing request and conversation IDs and returns the first two in response headers.

## Configuration

Configuration is validated through `pydantic-settings`. See `.env.example`. Supported providers are `fake`, `openai`, and `openai_compatible` (`openai-compatible` is accepted as an alias). Unknown providers fail at startup rather than silently falling back.

For OpenAI or another service implementing the OpenAI Chat Completions contract:

```dotenv
LLM_PROVIDER=openai_compatible
LLM_MODEL=your-model-id
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-secret-key
LLM_TIMEOUT=30.0
LLM_MAX_ATTEMPTS=3
```

The provider sends `POST {LLM_BASE_URL}/chat/completions`. It retries connection failures, timeouts, HTTP 429, and HTTP 5xx up to `LLM_MAX_ATTEMPTS`. Authentication and other HTTP 4xx errors are not retried. API keys, prompts, response content, and upstream error bodies are excluded from logs.

The adapter intentionally uses Chat Completions because it is broadly implemented by OpenAI-compatible providers. OpenAI's current documentation recommends the Responses API for new OpenAI-only applications; a future Responses adapter can be added behind the same `ChatModel` protocol without changing LangGraph.

`HMDP_BASE_URL` is not a readiness dependency. The shared HTTP client connects only when an integration operation is invoked. Authorization values are opaque and forwarded verbatim; the platform does not add a `Bearer` prefix.

## Docker

```powershell
docker build -t travel-agent-platform .
docker run --rm -p 8000:8000 travel-agent-platform
```

## Scope

This phase implements the platform boundaries, lifecycle, structured logging, minimal graph, fake and OpenAI-compatible models, tool infrastructure, HMDP transport, and tests. It intentionally excludes travel planning, recommendations, maps, weather, RAG, MCP business servers, memory, and multi-agent behavior. See [architecture](docs/architecture.md) and [existing-system findings](docs/existing-system-findings.md).
