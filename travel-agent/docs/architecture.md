# Agent Platform Architecture

## Context

Spring Boot remains the system of record and public business backend. The Python service is an AI runtime. It does not read the Java database directly and does not inherit Java transport models as agent-domain models.

```text
┌──────────────────────┐
│ Spring Boot / HMDP   │  users, shops, business data, authentication
└──────────┬───────────┘
           │ HTTP today; MCP may be added later
           ▼
┌──────────────────────┐
│ Integration Layer    │  transport, opaque auth, Result<T> parser,
│ HmdpClient + Adapter │  failure mapping, DTO → domain translation
└──────────┬───────────┘
           │ Python domain models only
           ▼
┌──────────────────────┐
│ Agent Platform       │  AgentService, AgentRuntime, request context
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ LangGraph Runtime    │  explicit, replaceable workflow
└──────────┬───────────┘
           ├──────────────────┐
           ▼                  ▼
┌──────────────────┐  ┌──────────────────┐
│ LLM Abstraction  │  │ Tool Registry    │
│ FakeModel today  │  │ + Executor       │
└──────────────────┘  └──────────────────┘
```

## Boundaries

### API layer

FastAPI handles transport validation and maps requests to `AgentService`. Routes never operate on a compiled graph directly. Request middleware establishes context variables so logs receive request and conversation IDs without threading logging fields through every function.

### Agent service and runtime

`AgentService` is the application-facing use-case boundary. `AgentRuntime` owns graph invocation and the execution error boundary. Streaming and checkpoint support can be added here without changing HTTP routes or graph nodes.

### Integration layer

`HmdpClient` owns connection reuse, timeouts, bounded retry for idempotent requests, opaque authorization forwarding, Java response parsing, and error mapping. Java's `Result<T>` envelope is integration-only. Adapters translate integration DTOs to Python domain models before agent code sees them.

Failures remain distinguishable:

- transport and HTTP failures become `IntegrationError` or `UpstreamTimeoutError`;
- HTTP 200 with `success=false` becomes `UpstreamBusinessError`;
- malformed JSON or envelope/data shapes become `UpstreamProtocolError`.

### Model and tools

The graph depends on a `ChatModel` protocol, not a vendor SDK. `FakeModel` enables deterministic local and test execution. `OpenAICompatibleChatModel` implements the Chat Completions HTTP contract using a lifecycle-managed connection pool. Provider configuration, authentication, timeouts, bounded retries, protocol parsing, and sanitized error mapping remain inside the adapter. Tool definitions hold an async handler behind a registry; the registry is independent of whether a later implementation uses a Python function, HTTP integration, MCP, or another external API.

The OpenAI-compatible adapter retries transient failures only: connection failures, timeouts, HTTP 429, and HTTP 5xx. It does not retry authentication failures or other request errors. Prompt text, generated text, API keys, and upstream error bodies are never logged.

### Lifecycle and readiness

FastAPI lifespan builds one lightweight application container. HMDP and LLM integrations use separate shared `AsyncClient` connection pools because they have different base URLs, authentication, and timeout policies. The clients, model, tool registry, compiled graph, and runtime are reused across requests and closed at shutdown. Readiness checks only components required by the current deployment. HMDP, Redis, Qdrant, and other future systems do not affect readiness merely because configuration fields exist.

### Observability

Instrumentation is represented by a small protocol and currently emits structured events. Agent and tool start/end events include latency. A future OpenTelemetry, Langfuse, or Prometheus implementation can extend this boundary without coupling domain logic to a vendor.

## Extension policy

RAG, MCP, memory, provider implementations, and product-specific graphs should be introduced as replaceable capabilities after their requirements are known. They must preserve the integration/domain boundary and should not make API routes responsible for orchestration.
