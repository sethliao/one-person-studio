# one-person-studio

> 一人动画制片厂：把「一个人 + AI 做出整季动画」的实战管线，沉淀成 25 个可直接调用的 Agent Skills。

**支持：WorkBuddy、Claude Code、豆包、Codex，以及其他支持 Skills 的 Agent。**

## 这是什么

这不是一个教程合集，而是一条**真实跑过、跑通、还在跑**的动画生产管线。

三个原创 IP（打工人题材 / 熊猫动画 / 海龟动画），EP1–EP5 已成片，全程一个人 + AI Agent 协作完成。生产过程中踩过的每一个坑——提示词写多长生成效果最好、静音判定阈值该设多少、哪些平台在收智商税——都被沉淀成了可复用的 skill。

- `agnes-video-prompt`：872 字长提示词实测优于短提示词，单秒成本 ¥0 的通道
- `ep-qa`：成片机器体检，静音阈值 −50dB 是实测标定值，不是拍脑袋
- `new-tool-triage`：见到新工具先走「只用/扩展/包装/抄」四选一，不重复造轮子

## 能力一览

| 环节 | Skills | 干什么 |
| --- | --- | --- |
| **总入口** | `ops` | 说清你的处境，自动路由到对的 skill |
| **立项** | `character-ip` · `content-strategy` | 角色 IP 档案与一致性 · 内容选题与栏目设计 |
| **生产** | `agnes-video-prompt` · `h3-prompt-writing` · `drama-episode-automation` · `design-codex` · `drama-claw-hermes` | 视频提示词写作 · 一 brief 一集 · 设计契约去 AI 味 · 本地管线 |
| **质检** | `ep-qa` | 画幅/时长/响度/黑帧/镜头密度，只报可测事实 |
| **调研** | `content-research-board` · `behance-research` · `behance-replicate-run` · `x-bookmarks-mining` · `social-account-diagnosis` · `studio-site-teardown` · `new-tool-triage` | 平台内容调研 · 对标拆解 · 收藏挖掘 · 账号诊断 · 新工具四选一 |
| **发布** | `behance-case-deck` · `social-media-archive` · `ai-handover-pack` · `library-pull` | 作品集案例页 · 社媒归档 · 知识库交接打包 |
| **商务** | `b2b-anchor-proposal` | 会议/大会/平台 To B 合作提案 |
| **工作流** | `frame` · `obsidian-auto-context` · `obsidian-plan-workflow` · `agent-skills-bridge` · `mcp-server-verify-mount` | 开工收工框架 · 会话记忆 · skills 桥接 · MCP 验证 |

## 安装

```bash
npx -y skills add sethliao/one-person-studio -g --all
```

或手动：

```bash
git clone https://github.com/sethliao/one-person-studio.git /tmp/ops-studio \
  && cp -r /tmp/ops-studio/skills/* ~/.claude/skills/ \
  && rm -rf /tmp/ops-studio
```

## 快速开始

安装后对 Agent 说：

```text
/ops 我想做一部系列动画，但只有我一个人。
```

或直接调用具体 skill：

```text
/ops-ep-qa 体检一下这四条成片能不能发
/ops-agnes-video-prompt 帮我写一个锁定角色一致性的提示词
```

## 状态

v0.1.0 · 首个公开版本，26 个 skills 上架。文档与场景指南持续补全中。

## 许可证

CC BY-NC 4.0 —— 个人学习与创作自由使用；商业用途需授权，联系作者。
