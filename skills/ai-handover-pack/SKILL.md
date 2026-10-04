---
name: ai-handover-pack
description: 把 Obsidian 知识库（ob_vault_s）编译成「平台中立」的交接包，交给不能读本地文件夹的外部 AI 平台（扣子/Coze、Kimi、豆包、GPTs、ChatGPT 自定义 GPT 等）。清洗掉 Obsidian 专有语法（双链 [[]]、嵌入 ![[]]、dataview、相对路径链接），按平台限制自动分段，输出可上传的知识库文件 + 系统提示词 + 工作流蓝图 + 回执模板，并打包 zip。当用户说"把知识库交给扣子"、"做个交接"、"交接给别的 AI"、"导出给 Coze"、"在别的 AI 上做视频生产"、"怎么把 skills 交给其他 AI"、"AI 交接包"时使用。
agent_created: true
---

# AI 交接包编译器

## 核心认知（先读这段，别跳）

**「交接」有两种，混在一起会做错。**

| 模式 | 对方 | 怎么做 | 注意 |
|------|------|--------|------|
| **A · 全库交接** | 能读本地文件夹的 agent（Cursor / Claude Code / Codex / WorkBuddy 另一空间） | 直接把 vault 路径给它 + 让它读 `System/AI交接协议.md` | 不需要导出包，**别多此一举** |
| **B · 导出包交接** | 只能吃上传内容的平台（扣子 / Kimi / 豆包 / GPTs） | 用本 skill 编译成交接包 | 见下 |

**模式 B 的铁律：交接包是编译产物，不要放进 vault 内部**（Obsidian 会把里面的 md 当笔记索引，污染搜索与双链图）。默认输出到 `~/Documents/ai-handover/<pack-name>/`。

**为什么必须编译，不能直接拖文件夹上传：**

1. `[[双链]]` / `![[嵌入]]` → 外部平台读不懂，链接背后的内容直接丢失
2. `dataview` 代码块 → 外部平台不执行，只是垃圾字符
3. `[文字](相对路径.md)` → 死链，换目录必断
4. 单文件超 5000 字符 → 超过平台单段上限
5. 塞太多无关笔记 → 稀释 RAG 召回，答得更差

## 平台限制（扣子/Coze，2026-09 官方文档）

| 项 | 上限 |
|----|------|
| 每个知识库文件数 | 300 |
| 单文件大小 | 100 MB（纯文本 / Markdown **5 MB**） |
| 单段长度 | 5000 字符 |
| 每知识库分段总数 | 10000 |
| 免费版容量 | 1 GB |
| 单智能体可绑知识库 | 150 |

## 用法

```bash
S=~/.workbuddy/skills/ai-handover-pack/scripts/build_handover.py
P=~/.workbuddy/binaries/python/versions/3.13.12/bin/python3

# 整包（改 config 里的 IP / 平台 / 文件清单）
$P $S pack --config ~/.workbuddy/skills/ai-handover-pack/packs/xiaohou-coze.json --force

# 单文件转换（快速验证清洗效果）
$P $S clean "path/to/note.md" -o /tmp/out.md
```

`pack` 产出：`00-系统提示词.md` · `01-知识库/*.md` · `02-工作流蓝图.md` · `03-交接回执模板.md` · `README-怎么用.md` · 同名 `.zip`

## config 结构

```json
{
  "pack": "小厚先生 · 扣子视频生产",
  "ip": "小厚先生",
  "platform": "扣子 / Coze",
  "out": "~/Documents/ai-handover/xiaohou-coze",
  "docs": [
    { "src": "源文件绝对路径", "as": "01-知识库/01-角色圣经.md" },
    { "src": "已经平台中立的文件", "as": "00-系统提示词.md", "clean": true, "split": false }
  ],
  "descriptions": { "文件名": "README 表格里的说明" }
}
```

- `clean: true`（默认）= 走 Obsidian 清洗；`false` = 只剥 frontmatter
- `split: true`（默认）= 超 4800 字符按 H2 自动切分

## 现有 pack

| config | 面向 | 输出 |
|--------|------|------|
| `packs/xiaohou-coze.json` | 小厚先生 × 扣子视频生产 | `~/Documents/ai-handover/xiaohou-coze/` |

换 IP 只要复制一份 config 改 `src` 清单——**系统提示词、工作流蓝图、回执模板在 `assets/` 里，是跨 IP 共用的骨架**，改里面的角色硬约束段即可。

## 清洗规则（`obsidian_to_plain`）

| 输入 | 输出 |
|------|------|
| frontmatter `---...---` | 删除，`title`/`name` 提升为 `# 标题` |
| `[[目标\|显示]]` | 显示 |
| `[[目标]]` | 文件名（去 .md） |
| `[[目标#锚点]]` | 目标（见「锚点」一节） |
| `![[媒体.png]]` | ［素材：媒体.png —— 二进制文件，未随本包导出］ |
| `![[笔记]]` | 当普通链接处理 |
| `[文字](相对路径.md)` | 文字 |
| `[文字](../assets/x.png)` | ［素材：x.png —— …］ |
| `https://...` | 原样保留 |
| ` ```dataview ` 块 | 整块删除 |
| `%%注释%%` | 删除 |
| `> [!note]` | 降级成普通 `>` 引用 |

## 交接的闭环

单向导出是不够的，必须约定**回流格式**，否则产出堆在外部平台落不了库。
`assets/03-交接回执模板.md` 就是干这个的——规定外部 AI 干完活要回填：
任务 / 产出物 / 关键参数（模型、消耗）/ **与原设定的偏差** / 待入库清单 / 链接清单。

拿到回执后（WorkBuddy 侧）：
1. 媒体 → `Assets/<IP>/generated/`
2. 分镜与提示词 → `001-Projects/<IP>/内容产出/`
3. 更新 `000-下一件事.md`
4. 可复用结论 → `HermesBrain/Memory/Decisions/`
5. 成本数据 → 汇总进三 IP 算总账

## 坑

- **别把包写进 vault 里**（见上，污染索引）
- **图片/视频实体不随包导出**，只在文字里留占位说明；要传图得单独上传到平台的「图片知识库」
- 知识库文件**宁少勿多**——RAG 召回会被无关内容稀释。一个 IP 控制在 6–10 个文件
- 系统提示词**不要塞进知识库**，它是「人设与回复逻辑」框的内容，两者机制不同
