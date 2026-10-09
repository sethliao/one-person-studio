---
name: character-ip
description: "Manage character IP projects: reference images, character profiles, consistency prompts, Obsidian. Use for 小厚先生/熊猫莫莫/Paikea or any original-animation IP: plan→interview→confirm→execute character updates, manage master-plate references, keep AI generation consistent."
description_zh: "角色 IP 项目管理：参考图、角色档案、一致性提示词。用于小厚先生/熊猫莫莫/Paikea 等原创动画 IP 的角色设定更新与 AI 生成一致性维护。"
version: 1.0.0
tags: [creative, character-ip, content-creation]
category: creative
---

# Character IP Management (WorkBuddy 适配版)

Manage a **character IP project** (小厚先生 / 熊猫莫莫 / Paikea) that involves AI-generated images/videos and this Obsidian vault. Covers reference management, character-profile updates, the plan→interview→confirm→execute loop, and generation consistency across styles/scenes.

> 迁移说明：由 Hermes `character-ip` 改写适配（2026-09-05）。旧 vault 路径 `080-Agent/…` 已更新为当前 `ob_vault_s` 结构（2026-10-05 改名）；`vision_analyze` 等 Hermes 专属工具改为通用能力。

## Core Workflow: Plan → Interview → Confirm → Execute

Always follow this sequence for character-IP updates.

### Step 1: Get the Reference
When the user provides a new reference image:
- Copy it into the vault's media library: `Assets/<IP>/角色设计/` with a descriptive name.
- **Read/inspect the image** (the agent can see images) and extract visual details: style, hair, eyes, face, clothing, expression, color palette, proportions.
- Document key findings before writing any plan.

### Step 2: Write a Plan in Obsidian
Create a plan at `HermesBrain/Plans/YYYY-MM-DD_<topic>.md` (frontmatter: `tags: [plan/active]`, `version`). Structure:
- **已完成动作** — what's already done
- **待办（确认后执行）** — checklist of updates
- **需要你确认的问题** — interview questions embedded (user answers in Obsidian)
- **执行顺序** — numbered steps

### Step 3: User Reviews in Obsidian
User edits the plan directly in Obsidian, answering questions. They say「写好了/执行」when done.

### Step 4: Execute Updates
Based on user answers:
1. Update the character profile (角色档案.md) in `Wiki/<IP>/`
2. Update character-design iteration records (角色设计索引 / Design.md) under the project's 素材 folder
3. Create/refresh a character-consistency prompt template for future AI generation
4. Archive / mark-old old character versions (move to Archive, don't delete)

## Vault Structure (current)

| 内容 | 位置 |
|---|---|
| 项目 hub / 工作区 | `Projects/<IP>/<IP>.md`（+ 故事源/分集日志/工作流/素材索引） |
| 角色档案 / 世界观 / 内容策略（常青知识） | `Wiki/<IP>/`（如 `Wiki/小厚先生/角色档案.md`） |
| 媒体文件实体（png/jpg/mp4/mp3） | `Assets/<IP>/`（角色设计/草图/表情包/videos/music） |
| 角色设计素材与索引 | `Projects/<IP>/素材/角色设计/` |
| 计划 | `HermesBrain/Plans/` |

> 短名链接 `[[名字]]` 引用；媒体内嵌 `![[Assets/<IP>/角色设计/xxx.png]]`。

## Character Profile Doc (角色档案.md)
Include: **基本信息** (name/age/appearance/personality/slogan), **诞生故事**, **创作者映射**, **情绪系列**, **视觉规范** (colors/fonts/composition/expression style), **语气指南**.

## Character Consistency Prompt & Master Plate
To keep the character consistent across styles (写实/卡通/3D/水墨), reference a single **master plate**:
- Master plate file lives in `Assets/<IP>/角色设计/` (e.g. 小厚先生: `小厚先生-主参考-角色定稿.png`).
- When generating images/video, pass the master plate as the reference image (image-to-image/video where possible).
- If using an image tool that supports a persistent reference id, record it in 角色档案 and this skill.
- If character design evolves: upload new plate → update reference → mark old version "旧版测试".

## Non-frontal Views → Character Sheet (⭐ 2026-09-21 定论)

**非正面视角（尤其背影镜）是这条管线唯一真正没解决的短板。** 有背面参考 → 背影镜成立；
没给 → 崩（小厚先生 C1 镜 4：凭空长出螺旋壳头发、脖子、耳朵消失）。

### ⭐⭐ 铁律：参考图话语权 ≈ 1 ÷ prompt 的指令密度

`/api/image/generate` **没有任何 ref 强度旋钮** —— 官方只收
`prompt / model / aspect_ratio / reference_images`（无序 base64 数组）/ `upscale`。
所以 **prompt 写得越自足，参考图越退化成「风格参考」**。

| prompt 长度 | 谁赢 |
|---|---|
| **688–1766 字**（场景镜头） | ✅ **参考图** → 身份锁死、逐特征零丢失 |
| **3947–4914 字**（"帮我画一张角色设定表"） | 🟡 **文字** → 只拿到服装/色板，结构比例全按文字走 |

**单变量 A/B 已验证**：同一条 230 字 prompt，带 ref = 参考图精确复刻；不带 ref = 一个无关的通用人形。

> ⚠️ **别让 AI 画整张设定表。** 4000 字的排版 prompt 会把参考图挤掉，三轮全崩（头发变竖香肠 / 变背头、
> 头身比漂、唇形变薄）。而且**长 prompt 会让模型偏科**：v2 里我堆了一串头发禁令，头发修对了，
> 头身比 / 腮 / 鼻 / 唇全被牺牲。
> ⚠️ **「模型画不对」先怀疑 prompt 太长，别先加描述。** 短 prompt 下模型自己就把头发抄对了 ——
> 我为「画对头发」折腾的三轮措辞全是多余的。

### ✅ 正确做法：拆两步（工具：`<vault>/004-Tools/char-sheet/`）

1. **AI 只出单视角图**，每条 prompt **≤400 字**，只写「同一个角色 + 一个机位 + 相机语言 + 材质 + 背景」。
   正面拿「3D 定稿全身 + 头部特写」两张干净图当锚；侧面/背面**拿刚出的正面图当锚**（同一次渲染的光与比例最一致）；
   特写喂正面 + 头部特写。参考各 IP 的 `prompts/` 目录。
2. **排版自己合成**：`scripts/build_char_sheet.py --ip <IP>`（Pillow，字体与色板读库根 `DESIGN.md`）。
   产物 `Assets/<IP>/角色设计/char-sheet/`。

⚠️ **喂的时候按镜头裁单张，别整张 sheet 当一张图喂**，并清掉 sheet 残留（字母 / 箭头 / 道具）。
⚠️ **抠底别自己写阈值**（试过阈值泛洪 + 色相判据+连通泛洪，两版都崩：近白背景漏吃、灰短裤与阴影被误吃）。
默认保留背景板；真要抠图走 MediaUse 的去背景。
⚠️ **色卡只认作者定的规范色**（`角色档案.md` 的视觉规范），别现场采样渲染图 —— 渲染图带光，
中位数会被卷发暗部拖成近黑，亮部百分位会被边缘光带跑。

取证全文：`Wiki/Research/参考图影响力实测-2026-09-21.md` · 工具文档：`004-Tools/char-sheet/char-sheet.md`

## Image / Video Generation (guideline)
- Media generation should be **GUI-first** (user clicks in DramaClaw/GFlow to save credits); ask before driving any paid API.
- For quick tests keep video short (~4s); longer (8-10s) for final.
- Consistency: always feed the master-plate reference image into image & video generation.

## Pitfalls
- **Test-data confusion**: distinguish test outputs (from outdated descriptions) from real reference. Update 角色档案 BEFORE generating new images.
- **Look at the image yourself** when one is provided — don't ask the user to describe it.
- **Plans in `HermesBrain/Plans/`**, user reviews in Obsidian.
- **YAML aliases**: when merging notes, add the old note's name to the target's `aliases` so the user can still find it.
- **Archive before delete**; version plans v1→v2 rather than overwriting.
