---
name: design-codex
description: 用本库的设计契约（DESIGN.md）约束任何对外视觉产出，并在出图后跑「AI 生成感」指纹审计。当用户说"做个海报/看板/案例页/PPT"、"排版"、"设计一套视觉"、"为什么我的东西看起来像 AI 做的"、"去 AI 味"、"统一视觉风格"时使用。也用于新建一个案子的视觉方向、或审计已有页面/看板的 AI 指纹。
agent_created: true
---

# 设计契约 + 指纹审计

**本库的对外视觉只有一份真源：`<vault>/DESIGN.md`。**
动手设计前先读它，出图后跑审计 —— 目标是把 AI 指纹从「一版几十处」压到 **0**。

## 为什么要有这个东西（2026-09-19 的发现）

Anthropic 官方 `frontend-design` 技能把「当前 AI 生成设计聚集的特征」写成了清单。
我们拿它审计自家的熊猫莫莫案（20 张看板 + 案例页），**命中 220 处**：

| 指纹 | 命中 | 症状 |
|---|---|---|
| 中间点拼的元信息串 | 129 | `MOMO · CASE STUDY · 2026` |
| 带空格的破折号标签 | 22 | `THE IP — CONCEPT` |
| 等宽字体做小数据标签 | 10 | 用时长的用 mono 排 |
| 全局同一个圆角 | 23 | 所有卡片 `radius=26` |
| 每张卡片同一个柔和灰影 | 4 | 层次被抹平 |
| 没有序列却硬编号 | 4 | 内容不是流程却写 01/02/03 |

这些单独看都合法，问题是**不管题目是什么都会出现** —— 所以它一眼就假。

判断一条到底是「选择」还是「默认」，用这个测试：
**拿一个完全不同的 brief 重跑一遍，如果还是长这样，那它就是默认。**

## 三条铁律

1. **先读 `DESIGN.md`，再动手。** 它是机器可读的（YAML frontmatter）+ 人可读的（正文）。
   改视觉 **先改这份文件**，再重跑渲染脚本 —— 不要在页面里逐个手改。
2. **中文当标题，英文当标签。** 这是本库的约定（也从 IP 的语言关系里长出来），
   而且刚好与英文默认相反 —— 于是它一眼就不像模板。
3. **出图后必跑审计，AI 指纹必须为 0。**

## ⭐ 交付闸门用 `design_audit.py`（不是 design_codex.py）

**2026-10-04 补建。** `DESIGN.md` 从 09-19 就点名它「出图必跑」，但文件从未被建出来 ——
本skill 之前写的「跑一次 design_codex.py 就够了」**不够**。

| | `design_codex.py` | `design_audit.py` |
|---|---|---|
| 定位 | token 解析 + 指纹引擎（库） | **交付闸门（CLI）** |
| 查什么 | 十条 AI 指纹（像不像 AI 做的） | 指纹 **+ 5 类质量**（会不会害到交付） |
| 用法 | `import design_codex as C` 取 token | `design_audit.py <file.html\|dir/>` |

```bash
P=~/.workbuddy/binaries/python/envs/default/bin/python
B=$VAULT_PATH/003-Workbench/_build

$P $B/design_audit.py path/to/page.html       # 审一个（交付前跑这个）
$P $B/design_audit.py some/dir/               # 审整个目录
$P $B/design_audit.py page.html --json        # 机器读
$P $B/design_audit.py page.html --only Q1,Q4  # 只查指定项
```
退出码：`0` 全过 · `1` 有硬伤 FAIL · `2` 只有 WARN

补查的5 类（指纹完全不查）：**Q1 对比度 AA** · **Q2 字体守约** · **Q3 字号字距可点区域** · **Q4 token 漂移** · **Q5 空标题空链接**

### 🚨 改这个审计器前必读：必须先在已知坏的样本上验证
>2026-10-04 实测踩坑：第一版把 `<style>` 一起剥了 → **Q2/Q3/Q4 静默返回 0 条**。
> 只拿自己的干净页面跑，会得到漂亮的「✅ 通过」，而实际根本没在工作。
> **「没报」和「没问题」长得一模一样 —— 这类静默失败最危险。**
>
> 负样本留在 `003-Workbench/runthrough/runs/2026-10-04-审美闸门/_negative-sample.html`，
> 改完审计器先跑它，看四类是否还能抓到。

⚠️ **必须用上面那个 python**（`envs/default`）。其他 python（含托管 3.13.12、系统 python）**没装 PyYAML**，
而脚本的兜底解析器在 2026-09-24 之前有 bug（`out, stack = {}, [(-1, out)]` → `UnboundLocalError`），
用错解释器会**直接崩**。该 bug 已修，现在任何 python 都能跑，但最终取数仍以 `envs/default` 为准。

在渲染脚本里消费 token：

```python
import sys; sys.path.insert(0, "$VAULT_PATH/003-Workbench/_build")
import design_codex as C

CREAM = C.hexc(C.TOKENS["colors"]["plush-cream"])
INK   = C.hexc(C.TOKENS["colors"]["plush-ink"])
RED   = C.hexc(C.TOKENS["colors"]["lantern-red"])
sp    = C.TOKENS["spacing"]            # rib / page-margin / gutter …
# 字体：C.FONTS["latin-black"|"latin-bold"|"latin-med"|"latin-reg"
#                |"cjk-reg"|"cjk-bold"] → (字体路径, face index)
```

## 十条指纹（审计器检测项）

| 编号 | 指纹 | 检测方式 |
|---|---|---|
| T1 | 全大写加字距的眉标 | `tracked(... "ALLCAPS")` / `class="eyebrow"` / `text-transform:uppercase` |
| T2 | 中间点拼的元信息串 | `\w+ · \w+` |
| T3 | 带空格的破折号标签 | `\w+ — \w+` |
| T4 | 等宽字体做小数据标签 | `F("mono"` / `font-family:Menlo` |
| T5 | 没有序列却硬编号 | `"01", font=` |
| T6 | 全局同一个圆角 | `radius=NN` 重复 / `border-radius:NNpx` |
| T7 | 奶油底 + 陶土色强调 | `#D9775x` / `#F4F1EA` |
| T8 | 纯黑文字 | `(0,0,0)` / `#000` / `#111` |
| T9 | 链接按钮挂箭头 | `→` |
| T10 | 每张卡片同一个柔和灰影 | `alpha=9x/1xx` |

### ⚠️ 元引用豁免（别误报）

正文里**讨论**某个指纹（例如把它写进说明表格、或引用别人的原话）不算**使用**它。
审计器会跳过 `<code>` / `<pre>` / `<script>` / `<style>` 里的内容 ——
所以要把「举例说明」的部分包进 `<code>`。

## ⚠️ 「指纹 0」≠ 合格（2026-09-24 实测补充）

十条指纹只管「**像不像 AI 做的**」，完全**不查**下面这五类 —— 别把 0 当成交付标准：

| 不查的 | 实例（2026-09-24 实测） |
|---|---|
| 对比度 | `momo-case.html` 有 8 处 `#fff9ee` 压 `#A39678` = **2.8:1**（AA 要 4.5:1） |
| 字体是否守约 | 同页主字体写了 **Inter**，而 DESIGN.md 要 Avenir Next、本文件注释明写「刻意不用 Inter」 |
| 字号/字距是否越界 | 工作台满屏 11.5px 正文 |
| 是否守 DESIGN.md token | 27 个页面共 792 处颜色/字号/圆角/字体漂移 |
| 标题层级 / 元素遮挡 / 破图 | — |

外部闸门（免费、纯本地、不调 LLM），要查上面这些就跑它：

```bash
export npm_config_cache=/tmp/npm-cache
npx -y impeccable@latest detect 003-Workbench/ --json    # 退出码 2 = 有硬伤
npx -y impeccable@latest detect <file> --no-design-system # 内部深色工作台建议关掉契约校验
```

⚠️ 它的 32 条 `slop` 审美规则会**误伤品牌决定**（把 `plush-cream #F8F1E5` 判成 cream-palette slop、
把 JS 填充的 `<img alt="">` 占位判成破图）→ 只用它的 29 条 `quality` 规则，slop 类只作参考。
完整规则表与评估：`003-Workbench/impeccable-评估-2026-09-24.md` ·
`003-Workbench/data/impeccable-rules.json`

## 这套是从哪来的（可追溯）

| 东西 | 出处 |
|---|---|
| `DESIGN.md` 约定 | Google Stitch（`stitch.withgoogle.com/docs/design-md/`） |
| 73 份现成契约 | GitHub `VoltAgent/awesome-design-md`（116,615 ★） |
| 设计哲学 → 画布 两步法 | Anthropic 官方 skill `canvas-design` |
| **十条指纹清单** | Anthropic 官方 skill `frontend-design` |
| 预设主题（10 套色板+字体） | Anthropic 官方 skill `theme-factory` |
| 开源版 Claude Design | GitHub `nexu-io/open-design`（97,010 ★） |

生态全貌与三平台扫描：`003-Workbench/design-ecosystem-2026-09.html`

## 新开一个案子的流程

1. 给**母题命名**（1–2 个词），从实物里取，不要从形容词里取。
   （例：莫莫的「灯与针」= 灯笼的骨架 + 角色脸上那道真实缝线）
2. 在 `DESIGN.md` 里改 token（颜色 / 字阶 / 间距 / 半径 / 组件规则 / Do's & Don'ts）。
3. 写渲染脚本，只从 token 取值，不写死字面量。
4. 跑 `design_codex.py` 审计 → 修到 0。
5. 回看上一版，**删掉一个元素**（出门前摘掉一件配饰）。

## 已通过审计的产出

| 产出 | 指纹 |
|---|---|
| `003-Workbench/design-ecosystem-2026-09.html` | **0** |
| `Assets/momo-case/`（2026-09-19 版） | 220 ← 待重渲 |

相关 skill：`behance-case-deck`（看板与案例页的排版流程）
