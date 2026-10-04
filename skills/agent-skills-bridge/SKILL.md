---
name: agent-skills-bridge
description: 盘点本机所有 agent 的 skill 目录，把「已经装了但 WorkBuddy 读不到」的 CLI / 插件原生 skill 用软链桥接进来，并检查断链。当用户说「你有没有用 XX 的 skill」「确保你有插件/CLI 原生的 skills」「装了新 CLI 之后帮我看看」「怎么这么慢/是不是能力没接上」，或发现自己在手动重造某个工具已有的流程时使用。
agent_created: true
---

# agent-skills-bridge

把散落在本机各处的 skill 收编进 WorkBuddy，并保证以后不再漏。

## 为什么需要它

WorkBuddy **只加载 `~/.workbuddy/skills/`**（外加项目级 `.workbuddy/skills/` 与 plugin cache）。
而 CLI 工具的 `install-skill` 子命令几乎只认 Claude Code / Cursor / Codex 等，
**从不写 WorkBuddy** → 结果是「工具装了、官方指南也在本机，但我不知道有它」，白走慢路。

2026-09-24 实测就踩了这个：opencli 的 6 个官方指南只装在 `~/.claude`、`~/.agents`、`~/.hermes`，
WorkBuddy 一份都没有。

## 一条命令体检

```bash
python3 ~/.workbuddy/skills/agent-skills-bridge/scripts/scan_skill_roots.py
```

输出四段：① 各 root 数量 ② WorkBuddy 已加载数 ③ 差集（外部有、WorkBuddy 没有）
④ **已装 CLI 对应的缺席 skill**（最该看的）。脚本为只读，不修改任何文件。

## 处理差集：先分类，别全搬

差集动辄上百个，**一股脑塞进去会污染 skill 列表、拖慢选择**。按这个顺序筛：

| 类别 | 处理 |
|---|---|
| **A. 绑定的 CLI 本机已装** | ✅ 直接 `ln -s`（脚本第 ④ 段就是这批） |
| **B. WorkBuddy 已有对等能力**（如 hermes→WorkBuddy、docx/xlsx/pptx 已有 tencent-*） | ⏭ 跳过，**在台账里写明"已有对等"**避免下次又纠结 |
| **C. 与该工具无关的历史 skill**（别的 agent 的专属技能、平台已废弃） | ⏭ 跳过 |
| **D. 高价值但不属 CLI 原生**（用户的创作/运营方法类 skill） | 🟡 **列给用户挑，不擅自装** |
| **E. 会与真源冲突的**（如从 vault 生成的 IP 角色卡） | ⚠️ **必须问** —— 双源会导致定义漂移 |

## 桥接（用软链，不要复制）

```bash
SRC=<权威源目录>
cd ~/.workbuddy/skills
ln -s "$SRC/<skill-name>" <skill-name>
```

**为什么软链**：上游 `skills update` / `npm i -g` 刷新源目录时自动跟随，零维护。

**权威源优先级**：

1. **该 CLI 自己的安装目录**（最权威，跟随 CLI 升级）
   - npm 包：`~/.local/lib/node_modules/<pkg>/skills/`
   - 例：`@jackwener/opencli/skills/`、`@volcengine/ark-cli/skills/`
2. **CLI 官方指定的 agent 安装位置**（如 `~/.claude/skills/`），当包内不含全部 skill 时用它
3. **`~/.hermes/skills/` 或 `~/.hermes/profiles/<p>/skills/<类>/<name>/`**（用户自己的定制 skill）

## 找 CLI 有没有自带 skill

```bash
<cli> --help | grep -i skill          # 1. 先问 CLI 自己
ls -d <npm-global>/<pkg>/skills      # 2. 再翻 npm 包
```

已知的坑与例外：

- ✅ `opencli skills list|read` —— 可列出/打印内置指南
- ✅ `hyperframes skills check|update` —— **例外：它自己会链 55 个 agent 目录，包含 WorkBuddy**，唯一免手动的
- ✅ `arkcli +connect` —— 装到所有检测到的 agent（但不含 WorkBuddy）
- ✅ `bsk install-skill` —— 同上
- ⚠️ 沙箱内跑 `<cli> skills update` 时，**批量删旧文件会被 safe-delete（50 文件阈值）拦下**，更新会半途失败。
  遇到就报告用户，在沙箱外重跑，别硬绕。

## 验证（必做）

```bash
# 穿透验证：软链是否真的可读
cd ~/.workbuddy/skills
for d in */; do n="${d%/}"; [ -L "$n" ] && { [ -r "$n/SKILL.md" ] || echo "❌ $n"; }; done
```

⚠️ 两个易错点：
- `[ -L "$d" ]` 里 **路径不能带尾部斜杠**（`for d in */` 的 `$d` 带 `/`，必须先 `${d%/}`），否则恒为 false。
- skill 列表在**会话开始时注入** → 新装的 skill **本轮读不到，下个会话才生效**。必须告知用户。

## 断链检查

已装的 skill 可能引用没装的兄弟 skill（如 `dbs` 主入口引用 `/dbs-update`）：

```bash
grep -rhoE "/[a-z0-9-]+-[a-z0-9-]+|dbs-[a-z-]+/" ~/.workbuddy/skills/dbs*/SKILL.md | tr -d "/" | sort -u \
  | while read s; do [ -e ~/.workbuddy/skills/"$s" ] || echo "断链: $s"; done
```

## 收尾（不可省）

1. 更新 `System/CLI-能力登记.md` §一·五「CLI 原生 skills 接入台账」—— 新 CLI 加一行（含源目录 + 一键刷新命令）
2. 遇到新坑 → 补进 `System/CLI-能力登记.md` §三
3. 更新 `.workbuddy/memory/MEMORY.md` 的 skills root 条目
4. append 当日 `.workbuddy/memory/YYYY-MM-DD.md`
