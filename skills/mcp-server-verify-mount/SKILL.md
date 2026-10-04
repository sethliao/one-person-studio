---
name: mcp-server-verify-mount
description: 验证一个 MCP server 是否真能跑（stdio 握手 + 列工具 + 盘点可用能力），再把配置合并进 WorkBuddy 的 mcp.json。当用户说"测试/安装某个 MCP"、"这个 MCP 好不好用"、"挂到 WorkBuddy"、"在 Cherry/Cursor 加 MCP 服务"、或贴来一份"MCP 安装教程"让你核实是否属实时使用。凡涉及第三方 MCP（reach-mcp、xiaohongshu-mcp、douyin-mcp、各平台爬取类）都应先跑本流程再回答，不要照抄教程结论。
agent_created: true
---

# MCP server：先验证，再挂载

## 为什么需要这个流程

网上流传的 MCP 教程经常**夸大覆盖范围**（说支持某平台，实际没有该 source）、
**说错认证方式**（说"浏览器登录即可"，实际要独立伴随服务 + 扫码）、或**推荐多余的中间层**
（让你装 Cherry Studio，而 WorkBuddy 本身就是 MCP 宿主）。
照抄教程会让用户白装一堆东西。所以：**先实测，用真实数据说话，再给方案。**

## 铁律：先计划后动手

用户明确要求"复杂任务先出方案、等批准"。所以：

1. 只做**只读探测**（起进程、握手、列能力）——这一步不改系统、不登录、不花钱，可以直接做。
2. 涉及**装软件 / 建 Docker / 扫码登录 / 写配置**，先出方案给用户选，批准后再动。
3. 探测完必须先给结论，再问下一步走哪条路（用 AskUserQuestion 给选项）。

## 步骤

### 0. 环境盘点（并行跑，一次问清）

```bash
ls -d /Applications/Cherry*.app 2>/dev/null        # 中间层是否已装
which uv uvx; which docker; which brew              # 依赖
ls ~/Library/Caches/ms-playwright/ 2>/dev/null      # playwright 浏览器（很多源的免费后端）
which <目标命令>
```

### 1. 只读探测：真跑一次，别信文档

用 `scripts/mcp_probe.py`（自带最小 stdio 客户端，只需标准库）：

```bash
~/.workbuddy/binaries/python/versions/3.13.12/bin/python3 \
  scripts/mcp_probe.py -- uvx reach-mcp --transport stdio
```

它会输出：`initialize` 结果（拿到真实 name/version）、`tools/list` 全部工具、
以及自动调用 `list_sources` 并汇总 **available / gated** 两组。

要点：
- **首次运行要下载依赖**，用 `run_in_background: true` 跑，别在前台等超时。
- 每个源常返回**独立 text block**（不是一个 JSON 数组），解析要逐条 `json.loads`，
  别直接当 `list[dict]` 用——这是最常踩的坑。
- `needs_auth=true` 但 `available=true` 说明模块已注册、后端待探测；`available=false`
  才是真的关着（gated）。

### 2. 实测一个免费源，证明它真的活着

不要只看 `list_sources`。挑一个免费源真搜一次：

```python
call("search", {"query": "关键词", "sources": ["bilibili"],
                "days": 90, "max_per_source": 5, "synthesize": False})
```

`synthesize=False` 拿原始行，避免因为没配 LLM 而失败或烧 token。
返回 0 条很正常（关键词太泛），要换更具体的关键词再试一次，别急着判死。

### 3. 写结论：教程声称 vs 实测

对每个用户关心的平台，明确给出三件事：**是否可用 / 需要什么凭证 / 走什么后端**。
凡是与教程不符的，直接标出来。

### 4. 合并配置（批准后）

WorkBuddy 的配置在 `~/.workbuddy/mcp.json`（**不是** `.mcp.json`）：

1. 先 `Read` 整个文件，看清已有 server。
2. 用 `Edit` 在 `mcpServers` 里**追加**一个 key，绝不覆盖已有的。
3. **command 用绝对路径**（如 `~/.local/bin/uvx`）。GUI 启动的宿主
   PATH 可能不含 `~/.local/bin`，写裸命令会启动失败。
4. 写形状与本文件已有条目保持一致（该项目风格是带 `"enabled": true, "disabled": false`）。
5. 写完**校验 JSON**：

```bash
~/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -c "
import json,os
s=json.load(open(os.path.expanduser('~/.workbuddy/mcp.json')))['mcpServers']
print(list(s.keys())); print('cmd exists:', os.path.exists(s['reach-mcp']['command']))"
```

6. **不要自己去启动 MCP**。告诉用户：新 MCP 不会自动生效，需要到连接器管理页
   右上角的自定义连接器入口点"信任"才会启用。

### 5. uvx 型 MCP 的通用配置模板

```json
"<name>": {
  "command": "~/.local/bin/uvx",
  "args": ["<pypi-package>", "--transport", "stdio"],
  "enabled": true,
  "disabled": false
}
```

## 已知结论（2026-09 实测，可直接复用）

`reach-mcp` v1.30.0，33 个源，零配置下 23 个可用：

- **可用**：arxiv, bilibili, bluesky, douban, dripstack, github, hackernews,
  lobsters, polymarket, reddit, stackoverflow, stocktwits, techmeme, toutiao,
  v2ex, weibo, youtube, zhihu
- **需凭证/伴随服务**：xiaohongshu（`XHS_MCP_URL`，需 xiaohongshu-mcp Docker + 扫码）、
  x（AUTH_TOKEN/CT0）、xiaoyuzhou、xueqiu、linuxdo、truthsocial、linkedin、
  quora、instagram、pinterest、threads（Apify）、tiktok、digg、rss
- ⚠️ **reach-mcp 没有"抖音"源**，只有 `tiktok`（TikTok 国际站）。
  中文抖音要另找 `douyin-mcp-server`。
- ⚠️ **小红书不吃 Chrome cookie**，走 Docker 伴随服务 + 手机 App 扫码。
- ⚠️ **B 站完全免费、无需登录**，"先登录 B 站"这一步是多余的。
- ⚠️ **Cherry Studio 是多余中间层**——WorkBuddy 本身是 MCP 宿主，直接挂即可。

## 常见坑

| 现象 | 原因 | 处理 |
|------|------|------|
| `parse failed: 'str' object has no attribute 'get'` | 源清单是多个 text block | 逐条 `json.loads` |
| 进程秒退 / `__error__: exited` | 命令不存在或 args 错 | 先用绝对路径手动跑一次 |
| 挂上后连不上 | PATH 缺 `~/.local/bin` | command 改绝对路径 |
| `search` 返回 0 条 | 关键词太泛 / 该源需凭证 | 换具体关键词；查 `sources_used` 里的 `gated_off` |
