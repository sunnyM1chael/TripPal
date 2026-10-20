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

Spring Boot 继续负责用户、商户、业务数据、Redis、Kafka 和数据库。Python 服务负责 Agent 执行、模型适配、工具基础设施和未来的 AI 能力。Python 不直接访问 HMDP 数据库。账号长期出行偏好由 Java 业务 MySQL 保存，会话、消息与任务摘录由 Python 独立 travel_agent 库保存；本地开发保留 SQLite 兼容。首次启用步骤见 [Agent 部署说明](travel-agent/README.md)。

## 目录说明

- `hmdp-plus/`：原 `hmdp-plus-master` 项目的源代码。构建产物、日志、IDE 配置和前端依赖没有纳入仓库。
- `travel-agent/`：Python 旅行助手，包含 FastAPI、LangGraph 基础设施、模型适配，以及商户查询、优惠券查询和探店预算规划工具。聊天入口为 `http://127.0.0.1:8000/assistant`，需配置支持工具调用的模型后使用真实业务能力。

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

