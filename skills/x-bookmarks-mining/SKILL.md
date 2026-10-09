---
name: x-bookmarks-mining
description: 只读抓取并分析 X/Twitter 的收藏(bookmarks)、点赞(likes)、关注(following)与任意用户时间线，输出结构化 JSON 并生成「按能不能跑分层」的可筛选看板；也能按用户已有的工具栈与已装 skill 筛出「直接能跑 / 换模型能跑 / 跑不了」的可跑清单；还能把收藏里带 mp4 的条目按主题铺成可直接播放的视频墙（零下载）。当用户说"抓我的 X 收藏"、"分析我的 Twitter 收藏"、"我 X 上收藏了什么"、"看看我收藏里哪些能用"、"哪些能用我现有的工具跑"、"帮我把能跑的视频列一下"、"我想看看生成视频的东西"、"分析我关注的是什么内容"、"抓一下 X 上的这个号"时使用。零 API key、复用已登录 Chrome、只读、不烧 credit。
agent_created: true
---

# X/Twitter 收藏挖掘

把 X 变成可分析的数据集。**走 opencli 的 `twitter` 适配器**（本地已装，163 个站点适配器之一），
复用已登录 Chrome 的 cookie —— 不需要 X API key、不需要开发者账号、只读。

## 0. 前置检查

```bash
O=~/.local/bin/opencli
$O twitter whoami            # 确认登录态，返回 logged_in: true + username
```

若 `logged_in: false` → 让用户在 Chrome 里登录 x.com，再重试（**不要**改用 `twitter login`，那是开浏览器等待登录，慢）。

## 1. 可用子命令（40+，只列常用的）

| 命令 | 说明 | 认证 |
|---|---|---|
| `bookmarks --limit N` | **登录用户的收藏**（newest first） | cookie |
| `likes [username] --limit N` | 点赞（默认登录用户） | cookie |
| `following [username]` | 关注列表 | cookie |
| `tweets [username] --limit N` | 某用户的推文（时序，去置顶） | cookie |
| `timeline --type following` | 首页时间线（`--type following` = 关注流） | cookie |
| `thread <url>` | 一条推的完整对话 | cookie |
| `search "关键词" --from X` | 搜索（映射 X 搜索运算符） | cookie |
| `profile [username]` | 资料：bio / 数据 | cookie |
| `trending` | 趋势话题 | cookie |
| `article`, `lists`, `list-tweets`, `notifications`, `download` | 长文 / 列表 / 通知 / 媒体下载 | cookie |
| `bookmark` `unbookmark` `like` `follow` `post` `reply` `retweet` | **写操作（UI 自动化）—— 除非用户明确要求，不要碰** | ui |

`--help` 里 `Access: read` = 只读；`[ui]` 标记 = UI 自动化，慢且会改动账号状态。

## 2. 抓取（关键：正确重定向）

```bash
O=~/.local/bin/opencli
$O twitter bookmarks --limit 5000 -f json > /tmp/x_bm.json 2>/dev/null
$O twitter likes     --limit 5000 -f json > /tmp/x_lk.json 2>/dev/null
```

⚠️ **必须用 `2>/dev/null`，绝对不要用 `2>&1`** ——
node 会往 stderr 打 `[UNDICI-EHPA] Warning: EnvHttpProxyAgent is experimental...`，
合并后会污染 JSON 导致 `json.load` 在第 1 行就崩。
（同理，别用 `time cmd | grep ...`，`time` 是 zsh 关键字，作用于整条管道。）

⚠️ **limit 给大值就行**，API 翻到没有更多会自然停（实测 148 条收藏用 `--limit 5000` 也只返回 148）。
实测 148 条约 6 秒。

**解析要健壮**（万一输出前仍有杂质）：
```python
raw = open(p, encoding='utf-8').read()
data = json.loads(raw[raw.find('[\n'):])   # 从第一个 "[\n" 开始切
```

## 3. 数据字段

```
id, author, name, text, likes, retweets, bookmarks, created_at, url,
has_media, media_urls[], media_posters[]
```
（`likes` 接口没有 `bookmarks` 字段。）

## 4. 分层规则（本 skill 的核心增值）

光有数据没用，用户要的是「**哪些能用**」。**顺序很重要 —— 先挖长文，再分层。**

### 4.1 先扫 t.co，这一步不能省 ⚠️

X 的正文里经常只剩一条 `t.co` 短链，**真正的正文在 X Article（长文）里**。
不展开就会把它误判成「没内容」—— 实测曾把 **31 篇长文误判为噪音**，用户当场指出。

```bash
# 展开短链（用 ThreadPoolExecutor 并发 8 路，138 条约 20 秒）
curl -s -o /dev/null -w '%{url_effective}' -L --max-time 20 <t.co-url>
```

指向 `x.com/i/article/<article_id>` → 是长文，走 4.2。
（也可能指向站外：`xbangdan.com`、`github.io`、别人的推文 —— 那些不算。）

### 4.2 抓长文全文

```bash
opencli twitter article "<tweet-url>" -f json     # 字段: author / title / content
```

⚠️ **必须传推文 URL（`x.com/<user>/status/<id>`），绝对不要传 article 页面 URL。**
传 `x.com/i/article/<id>` 会间歇性报 `Could not resolve article <id> to a tweet ID`
（实测 41 篇里 19 篇失败；改传推文 URL 后 **41/41 成功**）。
另加 1~2 秒延时避免限流。首轮冷启动约 8s/篇，热了之后 ~4s/篇。

### 4.3 然后分层

| 层 | 判据 | 含义 |
|---|---|---|
| **L** | 该条对应一篇已抓到全文的 X Article | 长文，信息密度最高 |
| **A** | 命中管线词：`minimax h3 seedance higgsfield fal topview omni veo 海螺 可灵 sora runway nano banana 世界模型 blender 3d cavalry three.js 建模 渲染 微缩 定格 stop motion previs vox 动画` | 贴现有管线，能直接复刻 |
| **B** | 命中工具词：`skill 工作流 workflow 开源 open source harness 插件 pipeline 流水线 codex cursor claude astra qoder agent github ide` | 装个工具/Skill 就能用 |
| **C** | 其余 | 只能当情报读 |
| **D** | 正文去掉链接后 < 15 字，**且不是 Article** | 真噪音 |

优先级 **L > D > A > B > C**。

> 教训：**不要用「抓到的字段」判断「内容的价值」。** D 类的正确定义是「短链展开后依然没东西」，不是「字段短」。

## 5. 落盘与出看板

```bash
python3 $VAULT_PATH/003-Workbench/_build/build_xbookmarks.py
```

读 `data/xbookmarks-*.json` → 生成三样东西：

| 产物 | 内容 |
|---|---|
| `x-bookmarks/index.html` | 主看板：卡片、L/A/B/C/D 筛选、关键词搜索、点赞作者榜 |
| `x-bookmarks/articles.html` | 长文库：左目录 + 右全文（`<details>` 折叠），可搜、按篇幅排序 |
| `x-bookmarks/articles/*.md` | 每篇长文一个 md（带 frontmatter），Obsidian 里可直接搜 |

脚本内含轻量 Markdown→HTML 转换 `md2html`（标题 / 列表 / 引用 / 代码块 / 行内样式）。
⚠️ 写这类转换时，**列表项之间的空行不能打断列表** —— 否则每个 `<li>` 会被单独包成一个 `<ul>`。

> 截图 / 图片走 `media_urls`（`pbs.twimg.com`，需联网）。用户偏好**不下载文件**，默认远程引用。
> 要离线可看再本地化到 `003-Workbench/media/`。

## 6. 分析套路（比数据本身值钱）

1. **收藏 vs 点赞 对照** —— 收藏 = 「我以后要用」（工具/变现焦虑）；点赞 = 「这打动我」（身份认同）。
   两者错位本身就是结论。实测该用户：收藏 39% 开源工作流 / 点赞 57% 3D 技术美术。
2. **主题用多标签计数**，占比会 >100%，注明是重叠加权。
3. **互动加权排序**：`likes×1 + retweets×3 + bookmarks×5`（收藏权重最高，最能代表"值得回看"）。
4. 产出落到 vault：分析笔记 `Wiki/Research/X收藏挖掘-<年月>.md` + 数据 `003-Workbench/data/`。

## 7. 按「用户已有能力」筛（把分层升级成可跑清单）⭐

L/A/B/C/D 分层回答的是「信息密度」，**不回答「我能不能跑」**。用户问「哪些能用我已有的东西跑」时，
要走这一节 —— 判据不是关键词，是**他的工具栈里到底有没有那台模型**。

### 7.1 口径：先写死用户的栈，再筛

```
模型侧：Google Flow（Nano Banana 2 / Veo 3.1 / Gemini Omni Flash）+ Grok Imagine + Meta AI
        + GPT Image 2 + 本地 Real-ESRGAN 放大
工具侧：Blender（本职）+ ffmpeg 合成管线（assemble_*）+ HyperFrames（HTML→视频）
        + MediaUse（bgm/sfx/voice/字幕）+ flow-music（Lyria）+ opencli（含 suno）
已装 skill 侧：kid_papercraft（儿童折纸定格 → 直接产出 Gemini Omni Flash 提示词）等
```

⭐ **「他已有的能力」= 模型订阅 + 工具 + 已装 skill 三者之和。**
⚠️ 最容易漏的是第三项：`kid_papercraft` 这个 skill 就躺在 `~/.workbuddy/skills/` 里，
目标模型正是他用的 **Gemini Omni Flash** —— 收藏里那条「儿童折纸定格动画」等于**零成本可跑**。
**筛之前先 `ls ~/.workbuddy/skills/` 扫一遍已装 skill**，别只盯着模型。

⚠️ **关键：他没订阅的模型一律不算**。2026-09 实测他**没有** MiniMax H3 / Seedance 2.5 /
Higgsfield / Topview / Kling / Runway / GPT-6 Astra —— 收藏里这几簇热度最高，但全是「跑不了」。
「热度高」和「你能跑」是两件事，**别让收藏数替他做决定**。

### 7.2 三档分流（看板按这三档分组）

| 档 | 判据 | 例（2026-09 实测） |
|---|---|---|
| **直接能跑** | 文里用的模型**就是他有的** | `Nano Banana 2 × Gemini Omni Flash` 微缩建筑（@Strength04_X）；`Omni 1.1 Flash` 角色一致性 prompt |
| **换模型就能跑** | 流程对得上，但某一步用了他没有的模型，且那步可替换 | Krea 找概念 → 换 Nano Banana；image2 透明底 → 换 GPT Image 2 端点 |
| **跑不了** | 核心模型他没有，且无法替代 | H3 / Seedance 2.5 / Astra 操控 Blender |

### 7.3 数据源优先级（**先读本地，别重复抓**）

1. **已抓好的长文全文**（`xbookmarks-articles-*.json`）—— 信息密度最高，**本地就能读，不联网**。先读这一层。
2. **收藏全文**（`xbookmarks-bookmarks-*.json`，2026-09-21 实测 **157 条**，会增长）—— `text` 字段短，但意图最强。
   ⭐ **收藏数低 ≠ 没用**：实测有一条 `bm=1` 的 Omni Flash 角色一致性 prompt，正好命中用户最大的痛点。
   ⭐ 其中 **67 条直接带 mp4**（`media_urls` 里是 `video.twimg.com/*.mp4`）——这批是「能看」那条轴的全部素材。
3. **点赞**（`xbookmarks-likes-*.json`）—— 实测倾向 3D/技术美术，**与用户的专业强项同侧，命中率反而高于收藏**。
4. **榜单**（`xlist-articles-*.json`，2700+ 条）—— **只有 title + excerpt，没有正文**。只能做粗筛，
   命中数天然偏低，别据此下「没人做 X」的结论。

### 7.4 产出：spec 驱动，别写死在脚本里

```
_build/specs/runnable-x.json   ← 人工判断写在这（分组 / why / 怎么用 / warn）
_build/build_runnable.py       ← 只做渲染，读 spec → x-bookmarks/runnable.html
```

**双轴版（§7.6）用这套**：
```
_build/build_xvideo_board.py   ← 顶部 RUNNABLE=[...] 是人工策展（tier/title/why/how/key），
                                 GROUPS=[...] 是「能看」那条轴的自动分组规则
                                 → x-bookmarks/video-picks.html
```
⭐ 策展条目用 `key` 字段（推文正文片段）**自动回连**到收藏数据，这样标题、点赞、URL 不用手抄，
收藏重拉后重跑即可。⚠️ 匹配时**必须 `lower()` 两边** —— 实测 `Cavalry` 匹配不上 `@cavalry__app`。
⭐ **判断（哪些能跑）必须人工过一遍**，关键词打分只是初筛（实测初筛 1195 条 → 人工收敛到 16 条，
精度差 70 倍）。脚本只负责渲染，下次改 spec 重跑即可。

每条卡片要写三样：**为什么算可跑** + **你该拿它做什么** + **⚠️ 坑**（账号/花钱/参数对不上的地方）。

### 7.5 顺手做两件事

- **覆盖率/盲区自检**：按技术栈分组扫一遍，命中最少的那个方向本身就是发现。
  实测「定格 / 微缩 / stop motion」在 2744 条榜单里命中 **0** —— 但这更可能是**该榜以中文区变现内容为主**，
  天然低估视觉手艺类，不能读成「这方向没人做」。
- **交叉印证旧结论**：筛出来的清单如果和「收藏 ≠ 点赞」的结论一致（值得跑的都在点赞那侧），
  就把它写进结论，帮用户校正内容方向。

### 7.6 双轴筛法：用户要「能跑」也要「能看」时 ⭐

实测用户会同时提两个要求（原话：「哪些是我真的能用上的，可以跑一下」+「不一定和我相关，
但我希望看到一些生成视频的东西，可以看一下」）。**这是两条轴，一张看板里都要有**：

| 轴 | 回答什么 | 怎么排 |
|---|---|---|
| **能跑的**（上半） | 我该动手做什么 | 按 §7.2 四档分流（L/A/B/C），每条写「为什么可跑 + 怎么跑 + 坑」 |
| **能看的**（下半） | X 上的人到底在做什么 | **按主题自动分组**（微缩定格 / 3D-Blender / 动效片头 / 商业片 / AI 短片 / H3 家族 / 教程 / 系统工具），组内按收藏数降序 |

⭐⭐ **带视频的收藏可以直接内嵌播放，零下载**：
`media_urls` 里的 `https://video.twimg.com/.../*.mp4` **可以直接当 `<video src>` 外链**
（实测 HTTP 200、`content-type: video/mp4`、`cache-control: max-age=604800`）。
→ **不要下载**（用户明确讨厌下载），直接 `<video controls preload="none" playsinline>` 铺成画廊。
实测 157 条收藏里 **67 条带 mp4**，一条命令就能做出「扫一眼就知道大家在做什么」的视频墙。

⭐⭐ **优先找「别人整理的目录」**：收藏里凡出现
**「榜单 / 精选 / 理了一下 / 整理成 / 合集 / 全开源」**这类词，命中一条顶十条。
实测一条 ★1604 的「0 出镜短视频 skills」榜单，一次给全 10 条玩法
（Vox 拼贴、儿童折纸定格、火柴人、数字人口播、3D 科普、国风动态画…），
比逐条翻收藏的效率高一个数量级。**筛之前先 grep 这些词。**

### 7.7 重拉时的增量策略（收藏会增长）

收藏数会变（148 → 157），别每次全量重抓长文。用 **`tweet_url` 里的 `/status/<id>` 与历史
`xbookmarks-articles-*.json` 比对**，只抓新增。
实测本轮 33 条「正文只有 t.co」里 **31 条可复用**，只需新抓 2 条（省 90% 时间）。
⚠️ 比对键要用 **status id**，不要用 `id`/`aid` —— 老库的字段名是 `aid`，直接对 `id` 会 0 命中。

## 8. 已知坑

- `bookmark-folders` 返回 **HTTP 404**：收藏夹是 **X Premium** 功能，普通号没有 → 直接走 `bookmarks`。
- `--top-by-engagement N` 可让 bookmarks 按互动加权重排。
- `twitter article` 传错 URL 类型会失败（见 4.2）；批量抓时加 1~2 秒延时防限流。
- 想看收藏里的媒体：`twitter download --tweet-url <url>`（会落文件，先问用户）。
- 遵守只读原则：**不要**自动 bookmark/like/follow/post。
- ⭐ 抓完先做一次**覆盖率自检**：统计「有正文 vs 只剩链接」的比例，别急着下「信息稀薄」的结论 ——
  漏掉的 31 篇长文就是这么被误伤的。
