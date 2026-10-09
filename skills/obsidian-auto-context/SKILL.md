---
name: obsidian-auto-context
description: "Session→vault auto-capture for the ob_vault_s knowledge base. At the end of a session (or on demand), capture findings, decisions, action items, and handover state into the vault's 000-下一件事 (single entry page), Daily notes, and AIbrain/Memory — with secret redaction. Turns disposable conversations into permanent searchable context."
description_zh: "会话自动沉淀到知识库：每次会话结束(或随时)把结论/决策/待办/交接点写入 000-下一件事、Daily 和 AIbrain/Memory，写前脱敏。让对话成为永久可检索的记忆。"
version: 1.1.0
tags: [obsidian, memory, second-brain, productivity]
category: productivity
---

# Obsidian Auto-Context（WorkBuddy 适配版）

Capture what an agent learns before it disappears. At the end of each WorkBuddy session in this vault, write the substance — findings, decisions, action items, and the handover point — into the vault as clean, linked Markdown so future sessions can retrieve it instead of rebuilding context.

> 迁移说明：改写自 Hermes `obsidian-auto-context`(SkillForge Labs, MIT)。落点已适配到本 vault 结构，并入已有的会话交接约定。

## When to use
- End of a research/analysis/creation session
- After making or recording a decision
- After creating/updating a skill or workflow
- Manually, any time the user asks to "存档 / 交接 / 记录"

## What it writes (per capture)
1. **000-下一件事.md** — update 「📌 现在到哪了」+ refresh the 「🔥 / ⏳ / 🧊」三块 (user opens this page first next time)
2. **Daily/YYYY-MM-DD.md** — today's progress under ✅今天 / 📌进行中 / 🎬项目进度 / 💡想法
3. **AIbrain/Memory/Decisions/** — new decision note when a decision was made (`YYYY-MM-DD-<主题>.md`, tags `[decision]`)
4. Optionally **AIbrain/Memory/Entities|Beliefs/** for durable knowledge
5. The agent's own `.workbuddy/memory/YYYY-MM-DD.md` daily log (append-only, machine layer)

> 所有写盘内容先过 `references/redact.py` 脱敏（API keys / tokens / 密钥），防止把凭据存进 vault。

## How it works
1. At session end (or on trigger), collect what happened: findings, decisions, action items.
2. Run text through `references/redact.py` to strip secrets.
3. Apply this vault's conventions:
   - wikilinks `[[短名]]`, not full paths
   - media stays in `Assets/` (referenced, not inlined in notes)
   - decisions → `AIbrain/Memory/Decisions/`
4. Write/update the files above (Edit existing; append to daily log).

## Capture note template (for a decision/entity note)
```markdown
---
tags: [decision]          # or entity / belief
created: YYYY-MM-DD
---
# 决策：<主题>
## 决策 / ## 背景 / ## 理由 / ## 何时重估 / ## 参考
```

## Conventions (this vault)
- **交接入口**：`000-下一件事.md`（**唯一入口**；原 `000-Handover.md` 已于 2026-09-29 并入本页，不要再找它）。每次会话结束刷新它的「📌 现在到哪了」与三块。
- Daily path: `Daily/YYYY-MM-DD.md`。Decisions/Entities/Beliefs under `AIbrain/Memory/`.
- Do NOT write to `~/Life/sync-vault/` (read-only main vault) or legacy `~/Documents/hermes-vault/`.
- Archive before delete; historical "Hermes" text in old notes stays untouched.

## Reference
- `references/redact.py` — last-line secret filter before writing to disk.

## Install note
This vault path is resolved at runtime from project memory (`ob_vault_s`); no hardcoded OBSIDIAN_VAULT_PATH needed.
