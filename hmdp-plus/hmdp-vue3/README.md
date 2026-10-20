# hmdp-vue3

## AI 旅伴

首页卡片和底部「AI 旅伴」进入 `/travel`。商户详情页的「让 AI 旅伴帮你看看这家店」会带入商户 ID，生成待发送的问题。聊天内的商户卡片可直接返回现有商户详情与优惠券页面。

同时运行 Java（8085）、Python Agent（8000）与 Vue 开发服务：

```powershell
cd F:\Projoct-code\旅伴\hmdp-plus\hmdp-vue3
npm install
npm run dev
```

`vite.config.js` 将 `/api` 转发到 Java，将 `/agent-api` 转发到 Python 并去掉该前缀。修改 Vite 代理配置后需要重启 `npm run dev`。模型密钥仅保存在 Python 的 `.env`，不进入 Vue 或浏览器。Vue 将当前业务登录令牌转发给 Agent，由 Agent 转发给 Java。

支持连续追问、停止等待、失败重试，以及基于真实工具结果的分类按钮、商户卡片、优惠券和预算摘要。聊天页增加城市选择、地图出行、历史对话、我的记忆。Python 独立数据库持久化会话与任务摘录，Java 业务数据库保存登录账号明确设置的长期偏好；访客只保存聊天历史。刷新后恢复历史；登录状态变化时清空浏览器内的旧账号内容，再按新身份加载。停止等待不保证模型请求立即终止，可从历史中重新打开查看生成结果。

`/travel/map` 提供城市地点搜索、起终点选择、驾车/步行路线、带路况的地图快照和导航入口。Python 需配置 `AMAP_API_KEY`（高德「Web服务」Key）；浏览器不持有地图服务 Key。持续定位、语音导航与实时路线重算由用户点击后打开的高德 App/H5 承接。

生产部署时需要在同源网关配置 `/agent-api/` 到 Python 的反向代理（去掉 `/agent-api`），读取与转发超时至少 130 秒。Vite 的 `server.proxy` 仅在开发模式生效。

```nginx
location /agent-api/ {
    proxy_pass http://127.0.0.1:8000/;
    proxy_read_timeout 130s;
    proxy_send_timeout 130s;
}
```

公开部署前应在 HTTPS 网关补齐入口级限流、跨域/来源策略和监控。Agent 已通过 Java `/user/me` 核验账号身份；匿名访客采用 HttpOnly Cookie。记忆数据按身份隔离，不能依赖客户端传入的用户ID。数据库部署和保留策略详见 `travel-agent/README.md`。

This template should help get you started developing with Vue 3 in Vite.

## Recommended IDE Setup

[VSCode](https://code.visualstudio.com/) + [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Customize configuration

See [Vite Configuration Reference](https://vite.dev/config/).

## Project Setup

```sh
pnpm install
```

### Compile and Hot-Reload for Development

```sh
pnpm dev
```

### Compile and Minify for Production

```sh
pnpm build
```

### Lint with [ESLint](https://eslint.org/)

```sh
pnpm lint
```
```bash
json-server  --watch  index.json
```
