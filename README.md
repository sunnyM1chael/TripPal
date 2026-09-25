# 旅伴

旅伴是一个单仓库项目，包含现有的黑马点评增强版业务系统和独立 Python Agent Platform。

```text
旅伴/
├── hmdp-plus/       # Java Spring Boot + Vue3 业务系统
└── travel-agent/    # Python FastAPI + LangGraph Agent Runtime
```

## 系统边界

```text
Vue3
  ↓
Spring Boot / HMDP
  ↓ HTTP / future MCP
Python Integration Layer
  ↓
Agent Runtime / LangGraph
  ↓
LLM / Tools
```

Spring Boot 继续负责用户、商户、业务数据、Redis、Kafka 和数据库。Python 服务负责 Agent 执行、模型适配、工具基础设施和未来的 AI 能力。Python 不直接访问 HMDP 数据库。

## 目录说明

- `hmdp-plus/`：原 `hmdp-plus-master` 项目的源代码。构建产物、日志、IDE 配置和前端依赖没有纳入仓库。
- `travel-agent/`：通用 Python Agent Platform，当前提供 FastAPI、LangGraph、FakeModel、OpenAI-compatible Provider、工具注册中心和 HMDP Integration 基础设施。

## 敏感配置

仓库不保存数据库密码、Redis 密码、LLM API Key 或本地 `.env`。

Java 服务通过环境变量读取：

```text
MYSQL_PASSWORD
REDIS_PASSWORD
```

Python Agent 的配置模板位于 `travel-agent/.env.example`，本地使用时复制为 `.env` 并填写实际值；`.env` 已被 Git 忽略。

## Python Agent 验证

```powershell
cd travel-agent
uv sync
uv run pytest
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

更详细的 Agent Platform 文档请查看 `travel-agent/README.md` 和 `travel-agent/docs/architecture.md`。

