# 旅伴 Travel Agent

基于现有 Spring Boot 业务接口的旅行助手。Python 负责模型与工具编排，通过 HTTP 查询 Java 业务服务，不直接连接业务数据库。

## 使用旅行助手

启动后打开 http://127.0.0.1:8000/assistant 。页面支持连续追问、新对话和查看工具查询依据。

- 按店名、商户分类查询，并筛选当前页人均预算。
- 查询商户详情、评分、地址、营业时间和优惠券。
- 按选定商户生成一日探店草案，计算人数对应的预计消费与预算差异。
- 按城市/区县搜索真实高德地点、查询驾车/步行路线、地图预览与高德导航。
- 持久化历史对话、出行偏好与跨会话相关片段回忆，可在 Vue「我的记忆」中管理。
- 原生 Function Calling：模型选工具 → 校验参数 → 查询 Java → 回传结果 → 再决定查询或回答。
- 每次请求最多 6 轮模型调用、10 次工具执行，总时限 120 秒。

先启动现有 Java 服务（默认 8085），再配置本目录 `.env`：

```dotenv
LLM_PROVIDER=openai_compatible
LLM_MODEL=你的支持工具调用的模型名称
LLM_BASE_URL=https://你的模型服务/v1
LLM_API_KEY=你的密钥
HMDP_BASE_URL=http://127.0.0.1:8085
```

不要把真实密钥写入 `.env.example` 或提交到 Git。默认 `fake` 只显示配置提示，不伪造商户数据。

新接口 `POST /api/v1/travel/chat`：

```json
{"prompt":"找人均100元以内的火锅店","conversation_id":null,"city":"南京"}
```

响应包含 `output`、`mode`、`tool_results`、`stopped`、`conversation_id`。后续请求必须带上返回的 `conversation_id`。服务端读取最近6轮对话，客户端 `history` 字段仅保留格式兼容，不用于替换服务端历史。Vue 刷新后从服务端恢复最近对话；价格与路线仍需重新查证。

`Authorization` 通过 Java `/user/me` 核验身份并转发，不发送给模型或存入记忆。`x-user-id` 不作为身份认证。访客使用 HttpOnly、SameSite=Lax 的随机 Cookie，数据库只保留其哈希。已登录身份核验失败时返回401，不回退到访客。默认每个身份每分钟20次聊天/地图请求；同一对话使用150秒租约防止并发写入。业务工具不执行下单、抢券或修改商户，记忆工具只写本人的出行偏好。

### 高德地图配置

在 [高德开放平台](https://console.amap.com/) 创建应用并添加「Web服务」类型 Key，将其填写到 Python `.env`：

```dotenv
AMAP_API_KEY=你的高德Web服务Key
AMAP_TIMEOUT=8
MEMORY_DB_PATH=data/travel-memory.sqlite3
MEMORY_RETENTION_DAYS=90
TRAVEL_REQUESTS_PER_MINUTE=20
```

该 Key 与百炼 Key 不同，无需加入 Vue 环境变量。需要允许行政区域查询、POI搜索、POI详情、路径规划与静态地图服务。未配置或额度/权限不足时明确返回错误，不提供虚构地点。API 使用官方 `city` + `citylimit=true` 限制城市范围。驾车使用 v5 路径规划，步行使用 v3；路线预览为带路况的静态地图快照，不持续追踪位置。用户点击导航后由高德 App/H5 提供持续定位、语音和实时重算。

### 记忆与部署

记忆按数据归属拆开：

| 数据 | 保存位置 | 身份与生命周期 |
| --- | --- | --- |
| 常用城市、预算、口味、饮食要求、出行方式 | Java 业务 MySQL 的 `tb_travel_preference` 分表 | 登录账号，通过现有登录校验；保留到用户修改或清除 |
| 会话、完整问答、工具结果、任务摘录 | Python 独立 `travel_agent` MySQL 数据库 | 按已核验账号或访客 Cookie 哈希隔离，默认90天 |
| 最近上下文 | 请求内从数据库读取 | 最近6轮原文 + 更早内容的有界摘录 |

访客可聊天和恢复当前浏览器的历史，保存长期偏好需要登录。Python 通过 Java `GET/PATCH/DELETE /user/travel-preferences` 访问偏好，不直接读取业务表，也不接受客户端指定的用户ID。面板只提交明确填写的偏好；聊天工具须本轮明确说「记住我的偏好」才允许写入。新对话不会清除账号偏好。

历史摘录是确定性的截取，最多10条，每条用户请求300字、旧回答160字；不是模型推断出的用户事实，可能丢失较早细节。每轮成功保存后更新，作为不可信历史上下文传入。跨会话回忆仍采用有界关键词匹配（最近200条候选、最多3条），不是向量语义检索。每段对话最多100轮，最多100段，列表最近50段。启动时清理过期会话。Redis 暂未接入，当前限流和生成租约落同一个会话数据库，多实例不依赖进程内锁。

#### 首次启用 MySQL

本机快速初始化与真实联调：在 `.env` 填好 `MEMORY_MYSQL_*` 并安装驱动后，于 `travel-agent` 目录执行 `.\.venv\Scripts\python.exe scripts\setup-mysql.py`。脚本仅创建 `travel_agent`、`travel_agent_test` 及其记忆表，并在测试库验证读写、用户隔离、生成租约、历史摘要和 SQLite 导入；不会修改 `.env`、删除原文件或访问 Java 业务库。账号需具备这两个库的创建及建表权限。所有 PASS 后，再按下方步骤停止旧服务、迁移现有历史并切换存储。Java 偏好表及登录接口需另行验证。

现有 `.env` 的模型和高德 Key 不需要更换。默认 `MEMORY_BACKEND=sqlite` 保留本地开发兼容；生产部署应按以下步骤明确切换，不会在 MySQL 连接失败时自动回退 SQLite。

1. **Java 重启前**，用数据库管理工具执行仓库 `hmdp-plus/sql/2_travel_preferences.sql`。该脚本只新增偏好分表。它覆盖现有 `hmdp_0`、`hmdp_1` 库，请在实际数据源主机分别核对执行；ShardingSphere 新规则按 user_id 路由。
2. 在 MySQL 新建独立数据库：`CREATE DATABASE travel_agent CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;`。给初始化账号该库建表权限；运行账号只需该库 SELECT/INSERT/UPDATE/DELETE，不需要业务库权限。Java 仍使用自己的业务数据库账号。
3. 在 `travel-agent` 目录安装可选驱动（核心 SQLite 依赖仍由原 `uv.lock` 管理）：

   ```powershell
   uv sync --frozen
   uv pip install --python .venv/Scripts/python.exe -r requirements-mysql.txt
   ```

   当前执行环境无法联网更新完整依赖锁，所以 MySQL 驱动使用独立可选依赖文件，未声称纳入核心锁。生产镜像默认安装该驱动；可用 `--build-arg INSTALL_MYSQL=false` 构建纯 SQLite 开发镜像。正式发布前应在联网构建环境固定该驱动及其 RSA 依赖版本。

4. 在 Python `.env` 中补充下列配置（密码只填本地文件，不提交 Git）：

   ```dotenv
   MEMORY_BACKEND=mysql
   MEMORY_MYSQL_HOST=127.0.0.1
   MEMORY_MYSQL_PORT=3306
   MEMORY_MYSQL_DATABASE=travel_agent
   MEMORY_MYSQL_USER=你的独立数据库账号
   MEMORY_MYSQL_PASSWORD=该账号密码
   MEMORY_MYSQL_POOL_SIZE=5
   # 远程 TLS 可填写 CA 路径，启用证书及主机名核验
   MEMORY_MYSQL_SSL_CA=
   ```

5. 用具备建表权限的账号运行 `uv run --no-sync python -m app.memory.admin init`；也可以直接在新库执行 `app/memory/mysql_schema.sql`。应用启动只检查已安装表结构，不自动建库建表。初始化后换回运行账号。
6. 停止旧 Python 服务。有旧 SQLite 数据时先备份，再运行：

   ```powershell
   uv run --no-sync python -m app.memory.admin import-sqlite --source data/travel-memory.sqlite3
   ```

   无旧文件则跳过。导入在目标库单事务内执行；同一源会话重复运行跳过，源数据变化或目标ID冲突会拒绝并回滚本次导入。不会删除或改写原文件，不复制访客或账号偏好到 Python MySQL。访客历史仍需原浏览器 Cookie 才能恢复，不能直接并入登录账号。
7. 旧账号偏好可单独迁入 Java：在当前终端设置 `TRAVEL_MIGRATION_TOKEN` 为该账号有效登录令牌，再执行 `uv run --no-sync python -m app.memory.admin import-preferences --source data/travel-memory.sqlite3`，随后清除该环境变量。工具先向 Java 验证当前账号，只读取其旧偏好；若 Java 已有偏好则拒绝覆盖，请在界面手动合并。不要把令牌写进命令参数或日志。
8. 重启 Java、Python 和 Vue；登录后在「我的记忆」保存偏好，刷新、新建对话、重启 Python 后检查恢复。MySQL 每个 worker 同时最多5条连接，事务结束即关闭；未使用常驻连接池。数据库的定期备份由部署方配置。

SQLite 仅用于本地开发；其旧 preferences 表仅保留供迁移工具读取，线上接口已改为通过 Java 保存偏好。SQLite 容器开发需挂载 `/app/data` 持久卷。生产访客 Cookie 为 Secure，必须通过 HTTPS。清除全部记忆会先清聊天历史再清 Java 偏好；这是跨服务操作，若第二步失败，接口明确提示“历史已清除、偏好清除尚未确认”，可重试，不承诺跨数据库原子事务。

新接口：`GET /api/v1/travel/state`、`GET/DELETE /api/v1/travel/conversations/{id}`、`PUT /api/v1/travel/preferences`、`DELETE /api/v1/travel/memory`、`GET /api/v1/maps/cities`、`GET /api/v1/maps/places`、`POST /api/v1/maps/route`、`GET /api/v1/maps/preview`。

### 能力边界

平台本地商户库仍按店名和分类查询，没有新增城市字段或自动导入高德数据。城市搜索使用高德 POI；`poi_id` 与平台 `shop_id` 完全独立，地图地点不承诺平台优惠券。预算筛选只针对当前页，不能宣称全城最佳。原 Java GEO 附近查询未改动。多点行程仍是探店草案；真实地图路线针对明确起终点提供驾车/步行方案，不包含多点全局优化、天气或预约。商户均价不是最终账单；优惠券金额按 SQL 定义由分转换为元。

后续方向：平台商户与真实城市数据治理、GEO附近查询、Redis缓存与入口限流、流式回复、可观测性与负载测试。当前实现和测试见 `app/memory`、`app/integrations/amap.py`、`app/api/travel_routes.py`、`tests/unit/test_memory.py`、`tests/contract/test_amap.py`。

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
- `GET /assistant` — 旅行助手聊天页面。
- `POST /api/v1/travel/chat` — 旅行业务工具调用循环，独立于原通用 LangGraph 验证接口。

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

The original platform architecture is retained. Travel endpoints add business tools, native function calling, Amap integration, user-scoped persistent memory, two on-demand travel skills and an optional local read-only MCP server. Weather, vector RAG, remote MCP account authorization and multi-agent execution are not implemented. The original skeleton design is recorded in [architecture](docs/architecture.md) and [existing-system findings](docs/existing-system-findings.md).

### 本次记忆改造验证

无需外部服务的检查：

```powershell
uv run pytest tests/unit/test_memory.py tests/unit/test_account_preferences.py tests/unit/test_config.py tests/unit/test_model_factory.py -m "not asyncio"
```

MySQL 集成检查需先初始化独立的、名称以 `_test` 结尾的测试库，再在测试终端环境变量中提供 `MEMORY_MYSQL_*`、`TRAVEL_TEST_MYSQL=1`，执行 `uv run --no-sync pytest tests/integration/test_mysql_memory.py`。测试故意不加载本地 `.env`，不允许使用默认业务/运行库；未配置时跳过。实际部署还需登录后的 Java → Python → MySQL 联调，不能用模型连通测试代替。

## 旅行 Skill

内置两个应用内 Skill，文件随项目版本管理，位于 `app/skills/bundled/`：

| 名称 | 工作流程 |
|---|---|
| `explore-food`（美食探索） | 明确城市、口味、人数和预算，查询真实餐馆，比较候选与平台优惠券，标明未知费用。 |
| `plan-relaxed-half-day`（轻松半日游） | 明确出发点和可用时间，少量停留点，查询相邻路线，保留休息并说明时间与费用缺口。 |

重启 Python 和 Vue 后，从 AI 旅伴欢迎页点击对应玩法即可。普通聊天会把技能名称与描述交给模型，模型需要时调用 `load_travel_skill`，服务器读取白名单中的 `SKILL.md` 正文后注入当前轮上下文；不会把所有技能正文常驻提示词。快捷入口通过 `skill` 字段明确选择技能。`GET /api/v1/travel/skills` 返回技能目录。

技能只指导方法，商户、价格、优惠券和路线仍需工具查询；不会增加工具权限，也不会自动保存用户偏好。不加载用户上传的 Skill，不执行技能中的脚本，不接受文件路径参数。加载过程保存在本轮工具记录中，历史对话可查看。它们是旅伴运行时的技能，未安装到开发助手的个人技能列表。

请求示例：

```json
{"prompt":"南京下午两点到六点，带爸妈别太累", "city":"南京", "skill":"plan-relaxed-half-day"}
```

接口返回 `loaded_skills`，表示本轮实际加载的技能。只加载技能不代表业务任务已完成；流程遵循效果还需要真实模型任务评测。可编辑行程卡等后续功能见 [TODO](docs/TODO.md)。

## 本机只读 MCP Server

MCP 是独立于网页服务的适配入口。当前 Vue 聊天继续直接调用本地工具；MCP 客户端通过 stdio 启动一个独立进程，两者复用 `TravelTools`，无须改造 Java 接口。

先安装可选依赖，正常网页运行不需要 MCP SDK：

```powershell
cd F:\Projoct-code\旅伴\travel-agent
uv pip install --python .venv\Scripts\python.exe -r requirements-mcp.txt
.\.venv\Scripts\python.exe scripts\test-mcp.py
# Java 启动后，可增加一次真实分类查询：
.\.venv\Scripts\python.exe scripts\test-mcp.py --live
```

兼容 `mcpServers` 配置格式的客户端可参考以下配置；路径需要按实际项目位置修改，不支持此格式的客户端则填写相同的 command 和 args：

```json
{
  "mcpServers": {
    "trippal": {
      "command": "F:/Projoct-code/旅伴/travel-agent/.venv/Scripts/python.exe",
      "args": ["F:/Projoct-code/旅伴/travel-agent/scripts/start-mcp.py"]
    }
  }
}
```

启动器会定位项目目录，再读取本地 `.env`，无需在客户端配置中复制模型或地图 Key。MCP 进程不调用千问，也不初始化记忆库。日志输出到 stderr；stdout 专供 JSON-RPC 使用。直接手动启动后等待输入属于正常状态，建议使用上面的测试脚本验证。

提供 9 个只读工具：`list_categories`、`search_shops`、`shops_by_category`、`shop_detail`、`shop_vouchers`、`plan_day`、`search_cities`、`search_city_places`、`plan_route`。前六项依赖 Java 服务；地图查询依赖高德 Web 服务 Key。工具标注为只读，参数由服务端模型校验，查询错误通过 `isError` 返回，避免向客户端暴露上游异常详情。

首版仅面向本机可信客户端，没有 HTTP 监听端口；不传入 Java 用户登录令牌，不开放偏好、私人聊天记录、下单、任意 HTTP 请求或文件访问。它不提供远程用户授权能力；远程部署和私人数据工具留待独立鉴权、限流及审计方案完成。

回归测试（MCP 测试在未安装 SDK 时会明确跳过）：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_travel_skills.py tests/integration/test_travel.py tests/integration/test_mcp.py
```

协议回归使用官方 SDK 的内存传输和模拟业务接口，验证初始化、工具发现、调用、参数拦截及错误脱敏，不代表真实 Java/高德联调完成。`scripts/test-mcp.py` 验证实际 stdio 子进程连接，带 `--live` 时再验证 Java 查询；外部客户端连接需要单独检查。
