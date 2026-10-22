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

当前源码不提交数据库密码、Redis 密码、LLM API Key 或本地 `.env`。
Java 的本机 `application.yml`、`shardingsphere.yaml` 已停止 Git 跟踪，已有文件保持可用。
首次克隆请从同目录的 `.example.yml` / `.example.yaml` 复制并在本地填写连接配置，
详见 [本机配置说明](docs/DEVELOPMENT.md)。历史提交中的旧配置未被重写。

Python Agent 的配置模板位于 `travel-agent/.env.example`，本地使用时复制为 `.env` 并填写实际值；`.env` 已被 Git 忽略。

## Python Agent 验证

```powershell
cd travel-agent
uv sync
uv run pytest
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

更详细的 Agent Platform 文档请查看 `travel-agent/README.md` 和 `travel-agent/docs/architecture.md`。

“驴友”新增多日行程规划：单城市1至7天，按每天分配地点，用高德计算站点间路线，逐日校验时间并核算全程预算。可在“我的行程”查看和调整，旧单日行程兼容；详见 [多日行程说明](docs/MULTIDAY_ITINERARY.md)。

已接入“优惠券候补”执行流程：驴友查询真实商户和券，准备操作卡；用户核对并确认后调用现有 Java 订阅接口，再回查状态，支持退出候补。候补可能自动发券并创建券订单，不是普通提醒。无需新增 Java 表，详见 [候补流程与验收](docs/VOUCHER_SUBSCRIPTION_FLOW.md)。

## 固定启动与新行程功能

以后以本仓库为开发与更新入口。根目录执行 `./dev.ps1 agent` 启动 Python，另一个终端执行 `./dev.ps1 web` 启动 Vue，`./dev.ps1 check` 检查服务。旧 Java 目录可暂时作为兼容运行副本，完整约定见 [开发与验收说明](docs/DEVELOPMENT.md)。

已增加“我的行程”：从高德地点生成并保存行程卡，可换店、删点、调顺序、调整停留和预算，支持标记完成及聊天中的途中调整。保存采用版本检查，已完成部分锁定。MySQL 需先运行 `python -m app.memory.admin init` 新增行程表，再重启 Python。

