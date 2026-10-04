---
name: content-research-board
description: 用 opencli 抓 B站/小红书/抖音/知乎/微博 等平台的结构化数据（零下载、零 token），再生成一页可内嵌播放的内容调研看板，或把 8–10 个平台的「收藏/赞过/稍后再看/Star/Pin」拉平成一本跨平台收藏总账。当用户说"帮我调研某话题"、"看看小红书上关于X的爆文"、"B站这个视频讲了啥"、"抓一下抖音文案"、"做个内容看板"、"把这些视频放一页里看"、"分析我的收藏"、"我在各平台收藏了什么"、"跨平台收藏分析"时使用。也覆盖「站点没有 opencli 适配器怎么抓」（opencli browser + 内部 resource API）与本地 HTML 看板的预览坑。优先走 opencli 而不是 reach-mcp —— opencli 复用用户已登录的 Chrome，覆盖小红书/抖音，且返回真实互动数据。
agent_created: true
---

# 内容调研 → 一页看板

## 为什么是 opencli（而不是 reach-mcp）

| | opencli | reach-mcp |
|---|---|---|
| 小红书 | ✅ 已登录 Chrome 即可用 | ❌ 需 Docker 伴随服务 + 扫码 |
| 抖音 | ✅ 有适配器 | ❌ **没有抖音源**（只有 TikTok 国际站） |
| 数据质量 | ✅ 返回真实热度（B站 `score: 86951`） | ⚠️ 无 LLM 时 score 全为 0 |
| token | ✅ 确定性 JSON，读取不烧 token | ⚠️ `synthesize` 要配 LLM 才工作 |
| 前提 | 需 Chrome 常开 + 登录 | 无需浏览器 |
| 定位 | **日常人在电脑前** | **无人值守/定时任务** |

结论：**opencli 为主**，reach-mcp 只在需要后台无浏览器运行时补位。

## 铁律

- **先计划后动手**：涉及登录/发布/下载的动作先问。只读抓取可以直接做。
- **不下载**：用户明确不要下载。只用 `-f json` 拿元数据 + 远程封面直链，不落任何媒体文件。
- **不烧 token**：opencli 输出是结构化 JSON，直接进上下文即可，**不要**再喂 HTML 给 LLM 总结。
- 发布类命令（`publish` / `post` / `delete` / `comment`）**必须**先拿到用户明确批准。

## 环境探测（先跑）

```bash
export PATH=~/.local/bin:$PATH
opencli --version
opencli list | head -40                       # 站点适配器清单
for s in bilibili xiaohongshu douyin zhihu weibo youtube; do
  echo "--- $s ---"; opencli $s whoami 2>&1 \
    | grep -vE "Could not create symlink|UNDICI-EHPA|trace-warnings" | head -4
done
```

`whoami` 返回 `logged_in: true` 才可用；返回 `AUTH_REQUIRED` 说明**需要在 Chrome 里登录该站点**。

### 已知登录态（2026-09-23 复检）

| 平台 | 状态 |
|---|---|
| bilibili | ✅ 已登录（志朋，id 20635174，Lv6） |
| youtube | ✅ 已登录 |
| xiaohongshu | ✅ 已登录（志朋Seth，1235 粉） |
| **douyin** | ✅ **已登录**（志朋Seth，id 110182150037，39 粉）—— 但 `search` 有适配器 bug，见下 |
| twitter / X | ✅ 已登录 |
| github | ✅ 已登录（`gh` CLI 也通，`gh search repos` 可搜仓库） |
| zhihu | ❌ 缺 `z_c0` cookie |
| weibo | ❌ 缺 `SUB/SUBP` cookie |

> 登录态会过期。**每次开工前重跑一遍 whoami**，别信这张表的日期。

### ⚠️ 小红书搜索必须加 `--site-session persistent`（2026-09-19 踩坑）

`whoami` 明明返回已登录，`search` 却报
`AUTH_REQUIRED: Xiaohongshu search results are blocked behind a login wall`。
**原因不是没登录，是默认会话是 `ephemeral`（一次性干净上下文，服务端判定为游客）。**

```bash
# ✅ 正确
opencli xiaohongshu search "黑客松" --limit 20 -f json --site-session persistent

# ❌ 会撞登录墙（即使用户已登录）
opencli xiaohongshu search "黑客松" -f json
```

`--window foreground` 更稳（后台窗口有时拿不到已完成渲染的页）。

> 📌 2026-09-23 复测：`opencli xiaohongshu search "AI短剧" -f json`（**不加** persistent）
> 这次直接成功返回 19 条。说明 persistent 并非永远必需 —— 但**撞墙时第一件事就是加它**。
> 稳妥起见：默认就带上 `--site-session persistent`。

### ⚠️ 小红书「笔记详情」必须传**完整签名 URL**（2026-09-20 踩坑）

`opencli xiaohongshu note <id>` 会报
`ARGUMENT: xiaohongshu note now requires a full signed URL`。
必须把 search 结果里那条**带 `xsec_token` 的完整 URL** 整个传进去：

```bash
# ✅ 从 search 结果里把 url 字段原样传进去（含 xsec_token）
opencli xiaohongshu note "https://www.xiaohongshu.com/search_result/<id>?xsec_token=...&xsec_source=pc_search" \
  -f json --site-session persistent
```

返回的是 `[{field, value}, ...]` 数组（不是对象），字段有
`title / author / content / likes / collects / comments / tags`。

### 报告必须可溯源（2026-09-20 新增铁律）

**任何给用户看的研究报告，每一条都要带「跳回原始出处」的链接。**
- X → `t.get('url')`（形如 `https://x.com/i/status/<id>`）
- 小红书 → search 结果里的完整签名 URL（带 `xsec_token`，需登录态）
- GitHub → `https://github.com/<owner>/<repo>`
- 推文里的 `t.co` 短链要用 curl 解析成真实地址再给：
  `curl -sS -o /dev/null -w "%{redirect_url}" --noproxy '*' --max-redirs 0 "https://t.co/xxx"`
- 没有链接的结论不要写。用户读报告时点不回去，就等于没做过。
**判断口径：`whoami` 通过 ≠ `search` 能用；两个都要跑一遍才算探测完成。**

### X / Twitter 可用命令（2026-09-19 实测）

```bash
opencli twitter search "关键词" --product top --limit 20 -f json
opencli twitter search "关键词" --product live --top-by-engagement 10 -f json
opencli twitter article <url>            # 长文（Article）导 Markdown
opencli twitter thread <url>             # 整条 thread
opencli twitter trending -f json
```
输出字段：`text / author / likes / retweets / replies / views / created_at / url / has_media`。
**排序建议**：X 原生顺序噪音大，用 `likes×1 + retweets×3 + replies×2` 自行加权。

### GitHub 两条路（都能用）

```bash
opencli github-trending repos --since weekly --limit 25 -f json
# ⚠️ github-trending 不接受 --window（会报 unknown option）
gh search repos "design system" --limit 12 --sort stars \
  --json fullName,stargazersCount,description,url
gh api repos/<owner>/<repo>/contents/<path> --jq '.[].name'
gh api repos/<owner>/<repo>/readme --jq '.content' | base64 -d
```

> ⚠️ `opencli github` 只有 `login` / `whoami`，**没有仓库搜索** —— 搜仓库用 `gh search repos`。

## 输出噪音要过滤

opencli 每次会打两行无用日志，**必须过滤**，否则 JSON 解析失败：

```bash
opencli bilibili search "关键词" -f json 2>/dev/null \
  | grep -vE "Could not create symlink|UNDICI-EHPA|trace-warnings"
```

### ⚠️ 更新提示行**有前导空格**，`^Update available` 过滤不掉（2026-09-23 踩坑）

实际输出是 `  Update available: v1.8.6 → v1.8.7`（**两个空格开头**）+ 下一行 `  Run: npm install ...`。
用 `grep -vE "^Update available"` 会漏掉它 → 写进 .json 尾部 → **`json.loads` 报错**。

```bash
# ✅ 两种写法都行
grep -vE "[[:space:]]*Update available|[[:space:]]*Run: npm"
```

**更稳的兜底**（不管什么杂质都能救）：写入后截到最后一个 `]` 再解析。

```python
raw = open(p, encoding="utf-8").read()
i = raw.rfind("]")
d = json.loads(raw[:i+1])          # 丢掉尾部任何非 JSON 尾巴
```

（`Could not create symlink ... EEXIST` 是 `~/.opencli/node_modules` 的无害警告，可以忽略；
沙箱环境里它还会报 `file-write-unlink` 被拦截，同样无害，命令本身已成功。）

### ⚠️ `--limit` 上限因站点而异（2026-09-23）

| 命令 | 上限 |
|---|---|
| `bilibili favorite` / `bilibili search` / `youtube watch-later` | 可到 400 |
| `xiaohongshu saved` / `xiaohongshu liked` | **100**（给 400 直接报 `ARGUMENT: --limit must be between 1 and 100`） |

拿不准就先给个小的，或从报错里读上限。

### ⚠️ shell 拆字符串别用 `set -- $cmd`（2026-09-23）

```bash
# ❌ 引号丢失 → error: unknown command 'bilibili favorite'（整串被当成一个参数）
for cmd in "bilibili favorite" "xiaohongshu saved"; do set -- $cmd; opencli $1 $2; done

# ✅ 用分隔符拆
for spec in "bilibili|favorite" "xiaohongshu|saved"; do
  opencli "${spec%%|*}" "${spec##*|}" --limit 20 -f json
done
```

## 常用抓取命令

```bash
# ---- B站 ----
opencli bilibili search "AI短剧" -f json            # rank/title/author/score/url
opencli bilibili video BV1xxxx -f json              # 含 thumbnail/时长/播放/点赞/收藏
opencli bilibili subtitle BV1xxxx  -f json          # 字幕（本次实测 3/6 可用）
opencli bilibili summary  BV1xxxx  -f json          # 官方 AI 总结（本次实测 1/6 可用）
opencli bilibili hot -f json                         # 热门

# ---- 小红书（需登录 + 建议 persistent 会话）----
opencli xiaohongshu search "AI短剧" --limit 20 -f json --site-session persistent
opencli xiaohongshu note "<完整签名URL>" -f json --site-session persistent   # 正文 + 互动
opencli xiaohongshu comments "<完整签名URL>"
opencli xiaohongshu creator-notes -f json            # 自己账号的笔记数据

# ---- 抖音（已登录，但 search 当前挂了，见下）----
opencli douyin search "关键词" -f json               # ⚠️ v1.8.6 报错，不可用
opencli douyin user-videos <sec_uid>                 # 备用路径，含下载地址和热门评论
opencli douyin hashtag "关键词"                       # 备用路径

# ---- 其它 ----
opencli youtube transcript <视频id>                  # YouTube 字幕
opencli zhihu search "关键词" -f json
opencli weibo hot -f json

# ---- 收藏夹 / 个人列表（「分析我的收藏」场景，2026-09-23 实测可用）----
opencli bilibili favorite    --limit 400 -f json     # B站收藏夹
opencli xiaohongshu saved    --limit 100 -f json --site-session persistent   # 小红书收藏
opencli xiaohongshu liked    --limit 100 -f json --site-session persistent   # 小红书赞过
opencli youtube watch-later          -f json         # YouTube 稍后再看（39 条）
opencli douyin collections           -f json         # 抖音「合集」⚠️ 不是「我的收藏」，见下
opencli zhihu collections            -f json         # 知乎收藏夹（需登录）
opencli weibo favorites              -f json         # 微博收藏（需登录）
opencli twitter bookmarks            -f json         # X 收藏 → 详见 skill x-bookmarks-mining
```

### ⚠️ `douyin collections` **不是**「我的收藏」（2026-09-23 澄清）

它返回的是**你自己创建的「合集」**（creator 侧，同「作品管理」），不是抖音的「我的收藏夹」。
Seth 账号实测返回 `[]` —— 那是**正确行为**（他没建过合集），不是通道坏了。

**结论：opencli 目前没有抖音「我的收藏」通道。** 想要只能走浏览器自动化
（`douyin.com/user/self?showTab=favorite_collection`）+ 页面 DOM 抓取，或用 BrowserSkill 兜底。
同类易混点：`douyin videos` = 自己作品列表，`douyin user-videos` = 指定用户的视频。

⚠️ `youtube watch-later` 会在 JSON **之前**先打一行 `Watch later  39 videos | No views`，
过滤时要一并去掉（或同样用「截到最后一个 `]`」的兜底）。

`-f` 支持 `table`(默认) / `json` / `yaml` / `md` / `csv`。**给 agent 读一律用 `json`**。

## ⚠️ 「看 B站视频摘要」的覆盖率真相（2026-09-23 实测 6 条样本）

| 命令 | 可用 | 失败形态 |
|---|---|---|
| `bilibili summary`（官方 AI 总结，含时间戳大纲） | **1 / 6** | `AUTH_REQUIRED: 访问权限不足 (-403)` ×4；`EMPTY_RESULT` ×2 |
| `bilibili subtitle`（字幕） | **3 / 6** | `EMPTY_RESULT` |

**关键判断**：`summary` 的 -403 **不是登录问题**（同账号下别的视频能出），而是**逐视频可用性**
（取决于该视频是否生成/开放了 AI 总结，通常短剧合集这类没有）。
→ **不要承诺"每个视频都能拿官方总结"**，拿到就算赚，拿不到就退到 `subtitle`，
再退就退到 `comments`（评论区常有人总结）。

## ⚠️ 抖音 search 在 opencli v1.8.6 是坏的（2026-09-23 实测）

即使 `douyin whoami` 返回 `logged_in: true`，`douyin search` 仍连环报两种错：

```
# 第一次：DOM 渲染超时
COMMAND_EXEC: Douyin search did not render result cards within the timeout.

# 加 --window foreground 后：适配器脚本自身抛异常
COMMAND_EXEC: Douyin search extraction failed:
  TypeError: Failed to execute 'observe' on 'MutationObserver': parameter 1 is not of type 'Node'
```

**这是 opencli 适配器的 bug，不是登录/cookie 问题**（`whoami` 明明白白通过）。
- 现状版本 v1.8.6，**v1.8.7 已发布**（可能已修，未验证）
- 升级属改动用户全局环境 → **先问 Seth 再升**
- 临时替代：`douyin user-videos`（需 sec_uid）/ `douyin hashtag`；或直接告诉用户"抖音这条暂时拿不到"

## ⭐ 没有适配器的站点怎么办 —— 用 `opencli browser`（Pinterest 实证，2026-09-23）

**先让 opencli 自己判断，别自己猜**：

```bash
opencli browser <session> analyze "<url>"
```

它返回 `pattern`（A/B/C/D）、`json_responses`、`api_candidates`、`nearest_adapter`、`recommended_next_step`。
Pinterest 的实测结论：**Pattern C —— 无 JSON XHR、无 SSR state，建议 HTML 渲染后抓**。

### Pinterest 配方（无适配器 → 内部 resource API 直取 JSON）

关键：**不要解析 HTML**。Pinterest 有内部 `resource/*/get/` 端点，
在**浏览器上下文里 `fetch`（带 cookie）** 就能拿干净 JSON，比 DOM 抓取稳得多。

```bash
opencli browser pinterest open "https://nz.pinterest.com/<username>/"
# 然后 eval 一段 async IIFE —— opencli 的 eval 会 await Promise
opencli browser pinterest eval "$(cat /tmp/pin_harvest.js)"
```

`pin_harvest.js` 的核心：

```js
(async () => {
  const post = async (opts, bookmark) => {
    const o = Object.assign({}, opts);
    if (bookmark) o.bookmarks = [bookmark];          // ← 分页游标
    const d = encodeURIComponent(JSON.stringify({ options: o, context: {} }));
    const r = await fetch(`https://nz.pinterest.com/resource/UserPinsResource/get/?source_url=%2F<username>%2F&data=${d}`, {
      credentials: 'include',
      headers: { 'x-requested-with': 'XMLHttpRequest',
                 'x-pinterest-pws-handler': 'www/[username]/index.js' }   // ← 缺这个头会 403
    });
    return r.json();
  };
  const base = { username: '<username>', field_set_key: 'grid_item', page_size: 50 };
  // 循环：读 resource_response.data[] + resource_response.bookmark，直到没 bookmark
})()
```

**字段要点（Pinterest grid_item）**：
- `title` / `description` **常常是空的** —— 别指望它
- ✅ **`auto_alt_text`** 是 Pinterest 自动生成的画面描述（"a young man standing next to a parking meter"）
  → **这是分类的主信号**，比 title 有用得多
- ✅ `board.name` / `board.url` —— 用户的 board 名本身就是强语义（如 `Family Photo reference`）
- ✅ `images["474x"].url` —— 可直接 `<img>` 嵌入（`i.pinimg.com` 允许热链）
- `pin id` → 规范链接 `https://nz.pinterest.com/pin/<id>/`（**原始对象里没有 url 字段，要自己拼**）
- `is_video` / `repin_count` / `created_at` / `dominant_color`

> **通用启示**：`opencli browser <session> eval` 是**万能通道** ——
> 站点没有适配器 ≠ 拿不到数据。先 `analyze`，再在浏览器上下文里找它的内部 XHR/API。
> 同类可复用：任何「登录后才可见」的列表页。

### 同源延伸：单张 Pin 也可以用同一套路

`opencli browser <session> analyze <url>` 已确认无防爬指纹（`anti_bot.detected: false`）。
所以流程永远是：**`analyze` → 判断 pattern → `eval` 拿 JSON**，不要一上手就写 DOM 选择器。

## ⚠️ 本地预览 HTML 看板的两个必踩坑（2026-09-23）

### 1. `opencli browser` 拒绝 `file://`，且**不绕过 `127.0.0.1`**

```
✖  Blocked URL scheme -- only http:// and https:// are allowed
# 换成 http://127.0.0.1:8899/x.html → chrome-error://chromewebdata/
```

**原因**：Seth 的 Chrome 挂了代理（opencli 自身也打印 `[UNDICI-EHPA] EnvHttpProxyAgent`），
代理**绕过了 `localhost` 但没绕过 `127.0.0.1`**。

```bash
# ✅ 起服务 + 用 localhost 访问
python3 -m http.server 8899 --bind 127.0.0.1     # 必须 run_in_background，否则随命令结束被杀
opencli browser board open "http://localhost:8899/x.html"
```

### 2. 重建 HTML 后浏览器**读缓存**，看到的还是旧版

症状：磁盘上已改，浏览器里行为没变。
**验证方法**：`opencli browser <s> eval "document.getElementById('...').options[0].textContent"`
—— 直接读出页面里的真实文案，和磁盘 grep 结果对比。

```bash
# ✅ 加时间戳穿透缓存
opencli browser board open "http://localhost:8899/x.html?v=$(date +%s)"
```

> 判断「是缓存还是我改错了」的通用手法：**先在浏览器里 eval 出真实值，再 grep 磁盘文件**。
> 两边不一致 = 缓存；一致但不对 = 自己写错了。别靠肉眼猜。

## 生成看板（v2 · 多平台）

```bash
python3 scripts/build_board.py [--keyword "AI短剧"] [--out content-board.html]
```

脚本**自动扫描** `data/` 下的这些文件，存在就加载，缺哪个就跳过哪个：

| 文件 | 平台 | 关键字段 |
|---|---|---|
| `data/board_data.json` | B站 | `bvid,title,author,cover,duration,publish,view,like,favorite,reply,url,rank` |
| `data/summaries.json` | B站 AI 总结 | `{bvid: [{time,content}] \| null}` |
| `data/xhs_notes.json` | 小红书 | `rank,author,title,content,tags,likes,collects,comments,published_at,url` |
| `data/dy_notes.json` | 抖音 | `rank,title,author,cover,content,tags,likes,comments,shares,published_at,url` |

页面能力：平台筛选 chips（可点击开合）· 关键词搜索 · 三种排序 · B站内嵌播放 ·
B站 AI 总结折叠展开 · **支持 `prefers-color-scheme`，浅色/深色都好看**。

> ⚠️ **页面数据必须由脚本从真实 JSON 生成，绝不手抄。** 手写会漏字段、会编出假封面 URL。
> 这是 2026-09-17 踩过的坑。

> ⚠️⚠️ **这条铁律同样适用于 Markdown 结论笔记**（2026-09-23 二次踩坑）。
> 写报告时**引用链接必须从数据里复制，不允许凭印象敲** —— 我曾在同一轮里编出一个
> YouTube `video id`（`JmE1kVbA_-k`），真实值是 `_rpCAll56F8`。
> **落地做法**：写完笔记后跑一次校验，把笔记里所有外部链接和数据集比对：
>
> ```python
> import re, json
> urls = {i["url"].rstrip("/") for i in json.load(open("data/collect/analysis.json"))["items"]}
> for u in re.findall(r"\]\((https?://[^)\s]+)\)", open(NOTE, encoding="utf-8").read()):
>     print("✅" if u.rstrip("/") in urls else "❌ 编的:", u)
> ```
>
> **结果必须 0 个 ❌ 才能交。** 这条比看板那条更容易漏，因为笔记看起来「像人写的」，不像机器产物。

### 内嵌播放的硬约束 —— 别踩

| 平台 | iframe 内嵌 | 做法 |
|---|---|---|
| B站 | ✅ | `//player.bilibili.com/player.html?bvid=<BV>&autoplay=1&danmaku=0` |
| YouTube | ✅ | `//www.youtube.com/embed/<id>` |
| 小红书 | ❌ | 禁止跨域嵌套 → **卡片 + 跳转链接** |
| 抖音 | ❌ | 同上 |
| 知乎 / 微博 | ❌ | 同上 |

**不要承诺"所有平台都能内嵌播放"** —— 只有 B站/YouTube 行。

封面图直链注意：B站给的是 `http://i1.hdslb.com/...`，要 **改成 https**，
并给 `<img>` 加 `referrerpolicy="no-referrer"` 防防盗链。
**小红书 search / note 都不返回封面字段** → 卡片走「文字优先」版式（标题 + 正文 + 标签 + 指标），
这对「爆文结构分析」反而更对路。

## ⭐ 进阶：跨平台「收藏总账」（把 N 个平台的收藏拉平成一页，2026-09-23 实测）

**问题**：人的收藏散在 8–10 个平台，每个平台口径不同（收藏/赞过/稍后再看/Star/Pin），
没法横向比较，「我到底在关注什么」永远答不上来。

**做法**：五件套 + 一条隐私红线 + 一道交付闸门。

| 组件 | 干什么 |
|---|---|
| `collect_all.py` | 6 平台**并发**抓取 + TTL 缓存 + 单平台失败隔离；支持 `--profile/--tag` 多账号分柜 |
| `fetch_covers.py` | 小红书封面回填（原生 `download` + 并发，只留第 1 张） |
| `analyze_collections.py` | 11 个来源 → 统一 schema → 去重 → **规则式关键词分类**（零 token） |
| `build_collections_board.py` | `analysis.json` → 单页看板（主题分布条 + 主题×平台热力矩阵 + 瀑布流卡片墙）；并把 `covers/` 同步到 HTML 同级 |
| `publish.py` | ⭐ **一键发布**：抓取 → 封面 → 分析 → 建板 → **同步进 vault** → 校验。**别手敲五步** |
| `verify_board.py` | ⭐ **交付闸门**：条数一致 / 无编造链接 / 本地封面真实存在。**0 个 ❌ 才算完成** |
| `PRIVATE_KW` / `PRIVATE_THEMES` | **隐私红线**：命中即整条排除出统计与建议 |

> ⚠️ **「同步进 vault」是最容易漏的一步，而且漏了不报错**。
> vault 里 `003-Workbench/data/collect/` 是**拷贝**不是软链，且多一个 vault 独有的 `picked.json`。
> 只重跑建板而不同步数据 → vault 看板读的是**旧 analysis.json**，页面上完全看不出来。
> → 所以统一走 `publish.py`，并且**同步时绝不覆盖 `picked.json`**。


### 关键设计决策（照抄这几条，别重新发明）

1. **规则式分类，不调 LLM**。理由：可复现、可审计、零 token、能解释「为什么这条归到这类」。
   代价：有误判（实测 GitHub `ant-design` 因描述含 "language" 被归入「教学·英语」）。
   → **所以只信「成规模的分布」，不信单条结论**，并在报告里写明这一点。
2. **隐私词表与选题词表分开维护**。不要因为「医疗内容也是内容」就放进 TAXONOMY ——
   私人健康问题被当成选题素材是**不可接受的错误**。要有一个独立的 `is_private()` 前置判断。
3. **「主动收藏」与「冲动点赞」要分柜**。X 收藏 157 vs 赞过 392 ——
   赞过是情绪体温计，收藏才是行动清单。混在一起会得出错的结论。
4. **自动抓取的池子（如 Behance 654）不能算「个人品味」**。报告里要显式剔除并说明。
5. **统一 schema 里务必带 `thumb`**（缩略图），否则看板是一堵灰墙。
   派生技巧：YouTube 由 `?v=<id>` 拼 `i.ytimg.com/vi/<id>/mqdefault.jpg`；
   GitHub 用 `https://opengraph.githubassets.com/1/<owner>/<repo>` 拿官方 og 卡片。
6. **卡片墙要按平台轮询交错**，不要按平台顺序排 ——
   否则没有缩略图的平台（小红书/知乎/微博/B站）会占满首屏，第一印象是一堆空白。
   **默认排序 = 平台轮询交错，且优先推带图的**（首屏立刻有视觉密度）。
7. **图片墙用 CSS 多列瀑布流，不要 `aspect-ratio` 裁切**：
   `columns:4 268px` + `.card{break-inside:avoid;display:inline-block;width:100%}` + `img{width:100%;height:auto}`。
   Pinterest 是**竖图为主**，用 `aspect-ratio:16/10;object-fit:cover` 会把竖图裁成一条，
   用户会直接反馈「Pinterest 的图片我看不到」——**其实是裁掉了，不是没加载**。
   `.more`/`.empty` 这类全宽元素要加 `column-span:all`，否则会被挤进某一列。
8. **本地图（小红书封面）与热链图（Pinterest）可以混用**，但本地图必须**连目录一起交付**：
   建板脚本负责把 `covers/` 同步到 HTML 同级，并在输出里打印 `本地封面 n/m 张`，
   方便一眼发现「看板生成了但图没跟过来」。

### 各平台收藏通道速查（2026-09-24 用 `opencli list -f json` 核对过签名）

> ⭐ **先跑 `opencli list -f json`，它是唯一权威**（1,275 条命令）。
> 下面这张表是快照，字段含义：`strategy` = 取数通道，`access` = 读写。
> 收藏类命令 **78 条，全部 `cookie`**（不存在「免登录拉自己收藏」这回事）。

| 平台 | 命令 | strategy | 关键参数 / 真实上限 | 实收 | 备注 |
|---|---|---|---|---|---|
| B站 | `bilibili favorite` | cookie | `--fid`（**不传只读第 1 个收藏夹**）、`--page`、`--limit` | 40 | ⚠️ registry 把它标成 `write`，实际是读；**多收藏夹必须用 `--fid` 逐个取** |
| 小红书 | `xiaohongshu saved` / `liked` | cookie | `--id`（可指定他人主页）、`--limit`；**无 `--page`** | 30+30 | 需 `--site-session persistent` |
| 小红书·图片 | `xiaohongshu download <完整URL>` | cookie | `--output <dir>`；**无封面字段** | — | 见下文「小红书封面」配方 |
| YouTube | `youtube watch-later` | cookie | `--limit` **上限 200** | 38 | 缩略图自己拼 `i.ytimg.com/vi/<id>/mqdefault.jpg` |
| 微博 | `weibo favorites` | cookie | `--limit` **上限 50** | 15 | — |
| 知乎 | `zhihu collections` → `zhihu collection <id>` | cookie | `--offset` + `--limit`（**每页上限 20**，可翻页） | 82 | 列表给 `collection_id`，再逐夹取 |
| **Pinterest** | ❌ **无适配器**（全表 grep `pin` 只有 `dianping`） | — | — | 91 | 只能 `opencli browser` + `UserPinsResource`，见上文配方 |
| X | `twitter bookmarks` / `likes` | cookie | ⭐ `--top-by-engagement N`（**内置加权重排**，别自己写） | 157+400 | 详见 skill `x-bookmarks-mining` |
| X·分夹 | ⭐ `twitter bookmark-folders` → `bookmark-folder <id>` | cookie | 同上 + `--top-by-engagement` | — | **把收藏按「意图」分柜**，比 148 条混着看有用得多 |
| GitHub | `gh api user/starred` | — | `--paginate` | 152 | ⚠️ 字段是 `url`/`stars`，**不是** `html_url`/`stargazers_count` |
| 抖音 | ❌ **无「我的收藏」通道** | — | — | 0 | `douyin collections` 是「我创建的合集」 |
| <em>（备选）</em> Instagram | `instagram saved` | cookie | `--collection`（按收藏夹）；**有适配器** | — | 本机未接，用户有 IG 时可扩 |
| <em>（备选）</em> Reddit | `reddit saved` | cookie | `--limit` | — | 同上 |

### ⭐ 「有没有一个开源的汇总 CLI？」—— 用注册表正面回答（2026-09-24）

用户反复问过这个问题。**别凭感觉答，跑一次 `opencli list -f json` 数出来**：

```bash
opencli list -f json > /tmp/ol.json     # 1.3 MB，只读注册表，不需要浏览器
python3 - <<'PY'
import json,collections
c=json.load(open('/tmp/ol.json'))['commands']
print(len(c),'条命令')                                   # 1275
print(collections.Counter(x['strategy'] for x in c))     # cookie 724 / public 338 / ui 182 / local 25 / intercept 6
PY
```

**结论（可直接复述给用户）**：

1. **不存在跨平台汇总命令**。1,275 条命令里每一条都绑定单个 `site`，没有 `all`/`aggregate` 这类入口。
   「一个 CLI 抓所有平台的收藏」在 opencli 里**是设计上没有的东西**，不是没找到。
2. **收藏类命令 78 条全是 `cookie`**。所以「换成 public 就能快」这条路**对收藏不成立** ——
   `public` 那 338 条是新闻/榜单/公开搜索类，读的是不需要登录的公开数据。
3. 因此真正的加速只能落在三处，**没有第四条**：
   - **缓存**（TTL 内不重拉，`collect_all.py --ttl`）
   - **并发 + 平台隔离**（一平台失败不拖垮全局）
   - **少调用**（一次 `--limit` 拉满，别逐条补详情）
4. 外部工具的诚实评估：`gallery-dl` / `MediaCrawler` / `panscrape` / `pinterest-dl` 确实各自覆盖多站，
   但它们是**下载器**，不是「收藏元数据汇总器」，且每个都会**新增一条独立的登录态**。
   - 用户明确说过「不用下载」→ 对收藏元数据这条路**不采用**。
   - 唯一值得留作后备的场合：Pinterest 封面 / 小红书封面，若 `xiaohongshu download` 失效可由 `gallery-dl` 接管。
   - **判定：不换。** opencli 已经是「带持久登录态的多站通道」这件事的最优解，换工具只是换一个登录面。

### ⭐ 小红书封面（本平台唯一没有缩略图的坑，2026-09-24 穷尽验证）

**已排除的六条路**（别再试一遍）：

| 路 | 结果 |
|---|---|
| `saved`/`liked`/`feed`/`note` 的返回列 | ❌ 固定字段里**没有封面**，也无 flag 可加 |
| 内部 feed API 直取 | ❌ HTTP `406 code -1`，要 `x-s` 签名 |
| 同源 fetch 笔记页 HTML 抽 `<img>` | ❌ 只有 38% 命中，且逐条很慢 |
| 笔记页 `og:image` | ❌ 是**常量占位图**（`picasso-static.../e6214e...png`），不是真封面 |
| `~/.opencli/cache/` 找 intercept 缓存 | ❌ 目录为空，只有 `browser-network/` |
| URL 正则取笔记 id | ⚠️ 会抓到**用户 id**；必须取**最后一个** 24 位 hex |

**✅ 正解：原生 `download` 命令 + 并发，只留第 1 张。**

```bash
# 一条笔记 14 张图 9 秒下完 → 我们只要 _1.xxx（文件名形如 <note_id>_1.jpg）
opencli --profile <profile> xiaohongshu download "<完整签名URL>" \
        --output <临时目录> -f json --site-session persistent
```

要点（`fetch_covers.py` 已实现，直接复用）：
- **并发**（3–4 workers）+ **按 note_id 跳过已缓存**；
- **只 `shutil.copyfile` 第 1 张**，其余 `shutil.rmtree` 掉临时目录（别把 14 张图堆在磁盘上）；
- 存成 `covers/<note_id>.jpg`，看板用**相对路径** `covers/xxx.jpg` 引用 →
  **`file://` 双击直接能看**，不依赖图床、不依赖登录态、不烧流量；
- 建板脚本负责把 `covers/` 同步到 HTML 同级目录（两处产物各自配套）。

**成本基准（诚实数）**：约 **17 s/条**（其中真实下载仅 ~9 s，其余是每次进程+bridge 启动开销），
60 条约 **20 分钟**。并发到 3–4 之后**基本线性失效** —— 因为 bridge 会在底层串行化，
`--workers` 只是排队，不会更快。**所以别加 worker，加缓存。**


> ⚠️ **读 JSON 前先验字段名，别照抄记忆里的字段**。
> 本次连续踩了三个：Behance 项目在 `items`（不是 `unique_projects`，那是计数）；
> GitHub 用 `url`/`stars`；X 显示名在 `name`（`author` 是 handle）。
> **动手前先跑一次结构探测打印 `list(d[0].keys())`**，比事后 debug 便宜得多。

## 完整流程（给别人讲的时候按这个顺序）

1. `whoami` 探登录态 → 缺哪个明确告诉用户去 Chrome 登录哪个站
   （`open -a "Google Chrome" "<站点URL>"` 直接帮他打开登录页，比自己念 URL 强）
2. `search -f json` 拿候选清单（只取标题/链接/热度，**不取正文**）
3. 挑前 N 条补详情（B站 `video` / 小红书 `note`）—— 逐条，只取需要的字段
4. `build_board.py` 生成看板
5. `present_files` 打开给用户看

## 常见坑

| 现象 | 原因 | 处理 |
|------|------|------|
| JSON 解析失败 | 混入了 symlink/UNDICI 日志 | `grep -vE` 过滤 |
| `Navigation rejected` | 未登录 / 需要先 `opencli <site> login` | 让用户在 Chrome 登录 |
| `AUTH_REQUIRED` | cookie 缺失或过期 | 同上 |
| 小红书 `blocked behind a login wall` | 默认 `ephemeral` 会话被判游客 | 加 `--site-session persistent` |
| 小红书 note 空返回 | 只传了笔记 ID | 传**完整签名 URL**（含 `xsec_token`） |
| B站 summary `-403 访问权限不足` | 该视频没有/未开放 AI 总结 | 非登录问题，退到 `subtitle` 或 `comments` |
| 抖音 search `MutationObserver` 报错 | **v1.8.6 适配器 bug** | 升级到 1.8.7（需先问用户）或换 `user-videos` |
| 封面 403 | http 直链 + 无 referrer | 换 https + `referrerpolicy="no-referrer"` |
| `command not found: timeout` | macOS 无 GNU timeout | 别用 timeout，直接跑 |
| `Blocked URL scheme` | `opencli browser` 不接受 `file://` | 起本地 HTTP 服务 |
| `chrome-error://chromewebdata/` | **代理不绕过 `127.0.0.1`** | 换 `http://localhost:<port>/` |
| 改了 HTML 但浏览器行为没变 | **浏览器缓存** | 加 `?v=$(date +%s)`；先 eval 出页面真值再 grep 磁盘对比 |
| `TypeError: 'int' object is not iterable` | 把「计数」字段当「列表」用（Behance `unique_projects`） | 先探测 `list(...keys())`，列表在 `items` |
| 报告里的链接点开 404 | **凭印象手写链接** | 写完跑链接校验脚本，必须 0 个 ❌ |
| 分类结果莫名（如 GitHub 仓库被归入「英语教学」） | 关键词误判（描述含 "language"） | 属预期；只信分布不信单条，并在报告里声明 |
| 后台跑的脚本日志一直是空的 | **Python stdout 被 pipe 缓冲**（`\| tee` 也会） | 用 `python3 -u script.py`，或别急着 tail |
| `nohup ... &` 起了进程却立刻消失 | 外层 shell 退出时子进程被回收 | 别用 `nohup ... &`；交给后台任务机制托管，或 `python3 -u ... \| tee` |
| `Multiple Browser Bridge profiles are connected` | 接了第 2 个 Chrome profile（如多账号） | `opencli profile use <name>` **不一定解决**；**稳的做法是每条命令显式带 `--profile <name>`** |
| B站只拉到 40 条就不动了 | `bilibili favorite` **默认只读第 1 个收藏夹** | 用 `--fid` 指定其它收藏夹 id，逐个取；`--page` 翻页 |
