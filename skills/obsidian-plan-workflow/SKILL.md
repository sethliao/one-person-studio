---
name: obsidian-plan-workflow
description: "Obsidian plan-driven execution discipline for WorkBuddy: how a plan in AIbrain/Plans becomes reviewed, approved, and executed, with status tracked via frontmatter tags + Dataview. Seth reviews & approves; WorkBuddy proposes & executes only after approval."
description_zh: "Obsidian 计划驱动执行约定：AIbrain/Plans 里的计划如何被审阅、批准、执行，用 frontmatter tags + Dataview 跟踪状态。Seth 审阅审批；WorkBuddy 提议，审批后才执行。"
version: 1.1.0
tags: [obsidian, workflow, plan-to-task, productivity]
category: productivity
---

# Obsidian Plan Workflow（WorkBuddy 适配版）

How a plan in this vault's `AIbrain/Plans/` becomes a reviewed, approved, executed task — tracked by frontmatter tags + Dataview.

> 迁移说明：改写自 Hermes `obsidian-kanban-workflow`(v1.0.0, Hermes Agent)。**已移除 Kanban/Gateway 依赖**（用户改用 Dataview 计划中心，语音驱动状态，不用 Kanban）。保留其执行纪律与安全规则。

## Core Rule
**Seth reviews & approves. WorkBuddy proposes. Never executes without approval.**

## The Flow (current vault)
1. Seth fills a plan / questionnaire in Obsidian (or says「计划：…」).
2. WorkBuddy writes the plan to `AIbrain/Plans/YYYY-MM-DD_<主题>.md` with frontmatter `tags: [plan/active]` + `version`.
   ⭐ **计划里必须有一张 Mermaid 框架图**（Seth 2026-10-05 定）：流程/架构长什么样——入口在哪、用什么工具、产物落到哪。
   跑完收工时补/改一张 as-built 版（实际跑成的样子），Plan 图 vs as-built 图的 diff 往往就是新理解。
3. Seth reviews in Obsidian (edit, check boxes, add notes).
4. Seth says「执行 / proceed」→ WorkBuddy reads the plan and follows the checked steps.
5. Results written back to Obsidian (outputs, notes, updates).
6. Status updated via **voice/chat**: Seth says「X 完成了」→ WorkBuddy edits frontmatter tags.
7. Dataview board ([[计划中心]] / Dashboard) refreshes automatically.

## Voice status updates
| 你说 | WorkBuddy 改 |
|------|------|
| "把 X 标记为进行中" | `tags: [plan/active]` |
| "X 在等反馈" | `tags: [plan/waiting]` |
| "X 完成了" | `tags: [plan/completed]` |
| "X 取消" | `tags: [plan/cancelled]` |

> 不用手动拖卡片——直接说，WorkBuddy 改 frontmatter，Dataview 自动刷新。

## Plan note template
```markdown
---
tags: [plan/active]
created: YYYY-MM-DD
version: v1
---
# 目标
一句话描述
# 步骤
- [ ] Step 1
# 你的反馈
> 写意见，然后说 proceed
```

## Safety Rules
1. **Never execute beyond the approved plan.**
2. **Seth must review before execution** — no auto-run.
3. **Every task linked to its Obsidian plan** for context (the plan file IS the source of truth).
4. **Version plans** v1→v2 rather than overwriting approved content.

## Conventions
- Plans live in `AIbrain/Plans/`; active/review via `计划中心.md` (Dataview MOC) and `Dashboard.md`.
- State is carried by frontmatter tags `#plan/active|waiting|completed|cancelled`.
- Big outputs go to files, not chat.
- Media generation stays GUI-first (Seth clicks to save credits).

## Pitfalls
- **Plan first, execute second.** Obsidian is source of truth; never skip the review step.
- **Don't auto-start long/agentic work** — present the plan and wait for「执行」.
- **External / paid / publish actions need explicit plan + approval first** (agent-rules).
