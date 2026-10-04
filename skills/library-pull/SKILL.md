---
name: library-pull
description: 把 WorkBuddy 资料库（workbuddy.cn / workbuddy.link）里的节点批量取回本地磁盘 —— 在线文档（kind=doc）转成干净 Markdown、网盘/历史媒体文件（smh/drive）直接下载、托管页面（web）拉 HTML 产物；也能在「我的文档」里建文件夹、把平铺的散件归位。同时覆盖「手机云端会话分享页」（`workbuddy.link/p/<id>`）的正文与产物提取。当用户说"把资料库的东西拿到本地"、"资料库文件下载下来"、"这个分享链接里有什么"、"云端会话电脑上看不到"、"整理资料库/建文件夹归位"、"资料库文档转 markdown"时使用。
agent_created: true
---

# 资料库 → 本地（取回 + 归位）

把云端资料库变成磁盘上的真实文件。**只读为主**；唯一的写操作是「建文件夹 + 移动节点」。

## 0. 三条存储默认互不相通（先理解这个，才能解释用户的困惑）

| 抽屉 | 在哪 | 谁能看见 |
|---|---|---|
| 会话工作目录 | 本地 = `mode=client`；云端 = 临时沙箱 | 只有那个会话，云端沙箱关了就散 |
| 资料库 | workbuddy.cn 云端空间，跨设备永久 | **必须显式去取**才可见 |
| 本轮对话附件 | 只在那一轮对话里 | 换一轮就掉 |

所以「手机上传到资料库 → 电脑上的对话看不到」是**正常现象**，不是 bug。
解法：在电脑端会话里**显式让我去资料库取**，或把分享链接贴过来。
反向同理：本地 vault 的内容手机云端也摸不到。

## 1. 前置：拿 token（客户端模式）

先跑 `runtime_context.py`：

```bash
SKILLDIR="~/Library/Caches/com.tencent.workbuddy.mac.BundleMigration/backups/WorkBuddy-5.5.4.38151288-1788946749595.backup.app/Contents/Resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/library"
python3 "$SKILLDIR/runtime_context.py"     # → KS_LIBRARY_RUNTIME {"mode":"client"}
```

- `mode=sandbox`（云端会话）：不取票，直接跑脚本。
- `mode=client`（桌面 + 本地 workspace）：**每次网络命令前**走
  `ToolSearch{tool_names:["connect_open_platform"]}` → `DeferExecuteTool{skill_id:"library"}`
  拿 `token`，再用 `--token-stdin` 通过 stdin 首行传给脚本。token 30 分钟有效，**不落盘、不复用**。

> ⚠️ token 过期后所有脚本只回一行 `{"error":"..."}`，看起来像权限问题，其实是没换票。**先换票再重试，只重试 1 次。**

## 2. 取回：三种 kind 三条通道

先 `space.workspace.node-info --node-id <id>` 拿 `kind`，再分流。

| kind | 通道 | 输出 |
|---|---|---|
| `doc` | `doc/get_doc_reviews.py --page-id <id>` | `KS_DOC_REVIEWS\t<id>\t<size>\t<url>` + 其后是**组件语法正文**（不是 Markdown！） |
| `smh` | `smh/get_download_link.py --node-id <id>` | `KS_SMH_DOWNLOAD {json}`（**空格分隔**），取 `download_url` 立刻下载（短期签名） |
| `drive` | `drive/entry.md` 的下载脚本 | 网盘文件 |
| `web` | `page/list_page_artifacts.py --node-id <id>` | JSON（`data.url` + `artifacts[].path`），拼起来 curl |

批量取回用 `scripts/pull.py`（见下）。

### 分享页 = 一个 web 节点

`https://workbuddy.link/p/<id>` 或 `www.workbuddy.cn/space/d/<id>` → `<id>` 就是 nodeId。
分享页产物里通常有 **`conversation-data.json`**（对话正文 + `artifactMap`）和 `index.html`：

```bash
python3 "$SKILLDIR/page/list_page_artifacts.py" --token-stdin --node-id "<id>"
curl -sL "<data.url>conversation-data.json" -o /tmp/conv.json
curl -sL "<data.url>index.html"            -o /tmp/conv.html
```

`conversation-data.json` 结构：`messages[]`（`content[]` 里 `text` / `tool-call`）+ **`artifactMap`**。
`artifactMap` 的 **key 是云端沙箱里的原始路径**、value 带 `nodeId` / `nodeKind` / `name` / `size`
——**这是定位「那批文件到底在哪个节点」最可靠的索引**，比按标题猜强得多。

> ⚠️ **分享页的产物不在资料库空间里**。`list-node` 那个 space 根目录通常只有这一个 page；
> `artifactMap` 里的 nodeId 各自散落在**独立的小空间**（`parentId == spaceId`），
> 用户界面看不到、也**不能跨空间 move**。需要落地就在本地重建结构，别指望搬得动。

## 3. 转换：组件语法 → Markdown

`doc` 取回的是 WorkBuddy 组件语法（`<Heading level="2">` / `<Mark bold>` / `<Table>` / `<BlockQuote>` …），
**必须先转成 Markdown 才能进 Obsidian**。用 `scripts/convert.py`。

组件全集（实测）：`Paragraph` `Heading` `Table/TableRow/TableCell` `BulletedList` `NumberedList`
`BlockQuote` `Code` `Divider` `Mark` `Todo`。

转换规则要点：
- `<Heading level="N">` → `#`×N；`<Divider/>` → `---`
- `<Mark bold>` → `**`；`<Mark italic>` → `*`
- `<Table>` → GFM 表格，首行当表头
- `<Code>` 内部**已经是 ``` 围栏文本**，直接去缩进输出，不要再包一层
- `<BulletedList>` / `<NumberedList>` **每个列表项是一个独立节点** → 连续同类节点要**接续编号、且不能插空行**
- 段落里行尾的 `\` 是硬换行 → `<br>`
- 正文末尾那行 `KS_DOC_REVIEWS\t...` 要丢掉；开头 `---\ntitle: xxx\n---` 也要丢掉（另写 frontmatter）

## 4. 归位：资料库建文件夹 + 移动节点

`mutation.md` 规则：**目标是「我的文档」（category=personal）且用户已明确要求 → 直接执行，不用二次确认**；
只要有一个目标是团队空间才需要停下确认。

```bash
python3 "$SKILLDIR/manage/create_folder.py" --token-stdin --title "工具" --space-id "<spaceId>"
python3 "$SKILLDIR/manage/create_folder.py" --token-stdin --title "scripts" --space-id "<spaceId>" --parent-id "<父id>"
python3 "$SKILLDIR/space_api.py" space.workspace.move-node --token-stdin --node-id "<id>" --target-parent-id "<目标文件夹id>"
```

- 输出格式：`KS_FOLDER_CREATE\t<id>\t<kind>\t<url>` ——**制表符分隔，不是 JSON**，别用 `json.loads` 直接解整行。
- 同名文件夹可能已存在（重跑）→ **先 `list-node` 查子节点，同名就复用**，否则会堆一堆重复文件夹。
- **跨空间移动不支持**，只能同空间换父。
- **删除没有 API**（文件/文件夹都不行），只能改名或移动，别承诺清理。

## 5. 脚本

```bash
# 批量取回（spec 里写清每个节点去哪）
LIB_TOK="<token>" python3 scripts/pull.py --spec spec.json --out /tmp/pull

# 组件语法 → Markdown（单个或整目录）
python3 scripts/convert.py --src /tmp/pull/raw --out /tmp/pull/md
```

spec.json：

```json
{
  "items": [
    {"path": "工具/SKILL.md",  "node_id": "xxxx", "kind": "doc"},
    {"path": "工具/run.py",    "node_id": "yyyy", "kind": "smh"},
    {"path": "工具/report.html","node_id": "zzz", "kind": "web"}
  ]
}
```

## 坑（都踩过）

1. **`--cities $VAR` 在 zsh 里不拆词** → 整串被当成一个参数。用 `${=VAR}` 或写进脚本。
2. **大批量网络请求会被杀**（SIGTERM / exit 137）。分批 + 后台跑，别指望一次跑完 70 个请求。
3. **短名链接要求文件名全库唯一**。多个工具都有 `data-sources.md` / `report-template.md` → 落地时加
   **工具名前缀**（`资本周期-数据源.md`），并在 Hub 页留一张「原名 → 新名」对照表。
4. **重名节点靠题目猜不出来**（两个 `data-sources`、两个 `SKILL`）→ 读第一行标题正文来判归属：
   `get_doc_reviews.py | grep -A2 '<Heading' | head -5`。
5. 取回的二进制如果只有一份、又属于某个工具，**跟着工具走**（`004-Tools/<工具>/reports/`），
   别硬拆进 `Assets/`——拆了工具就不「开箱即跑」了。
