---
name: behance-research
description: 只读抓取 Behance 的搜索页/项目页/个人主页/团队主页/moodboard/关注列表，输出结构化 JSON+CSV，用于趋势分析、工作室画像、自我诊断、AI 内容盘点、品味画像和「复刻说明书」。当用户说"抓 Behance"、"Behance 趋势"、"Behance 上有人传 AI 吗"、"分析这个工作室"、"拆解这个项目"、"看我的 Behance 数据"、"看我关注了什么"、"Behance moodboard"、"Behance 调研"时使用。零第三方依赖、只读、不破解签名。
agent_created: true
---

# Behance 取数层（只读）

把 Behance 变成可分析的数据。**服务端渲染，curl 就能拿每类页面的首屏**——不需要浏览器、不需要登录态（公开内容）。

## 四条命令

```bash
S=~/.workbuddy/skills/behance-research/scripts/behance_fetch.py
P=~/.workbuddy/binaries/python/versions/3.13.12/bin/python3

$P $S search    --field "3d art" --search "panda" -o out.json --csv out.csv
$P $S project  245233547  -o out.json          # 也可传完整 URL
$P $S profile  dcpproduction -o out.json       # 个人主页
$P $S profile  dcpwork      -o out.json        # 团队主页（同一命令，自动识别）
$P $S moodboard 226764113   -o out.json        # 也可传完整 URL
$P $S --delay 1.5 ...                          # 请求间隔（默认 1.5s，别调低）
```

JSON 打到 stdout，摘要打到 stderr，`-o` 落盘。**给 agent 读一律看落盘文件**。

## 实测结论（2026-09-19，别再验一遍）

| 维度 | 结果 |
|---|---|
| 页面渲染 | ✅ 服务端渲染，curl + 普通 UA 即可，无需浏览器 |
| `field=` 领域筛选 | ✅ **唯一有效的切分维度** |
| `search=` 关键词 | ✅ 有效 | 
| `field=` + `search=` 叠加 | ✅ 有效且**返回新结果**（与纯 field 0/24 重叠） |
| `tools=<工具ID>` | ✅ **真过滤**（按「项目填写的工具」筛）——**这是抓 AI 内容的唯一可靠入口** |
| `q=` 关键词 | ❌ **被静默忽略**（不是 `search=` 的别名，别用） |
| `user_tags=` 标签 | ❌ **被静默忽略**（`user_tags=ai` 与 `user_tags=zzzznonsense` 返回一模一样，同 `q=` 的坑） |
| `&page=N` 翻页 | ❌ 完全无效（搜索页、主页一致，返回同样内容） |
| `&sort=` / `&time=` / `&owners=` | ❌ 无效（sort 直接返回 0 结果；owners 返回通用热门，**不是**该作者作品，别把推荐位当结果） |
| 私密 moodboard | ❌ 未登录返回 **HTTP 404**（服务端判定，非前端遮罩；带登录态才可读） |
| 非本人 moodboard | ⚠️ 只 SSR 首批，`collection.isItemsLastPage` 判断是否还有更多 |

### AI 内容怎么抓（2026-09-19 新增）

- Behance **没有「AI 披露」字段**（项目 JSON 38 个字段里没有 AI 相关项）。判断是否 AI 只能靠 **tools**（硬证据）和 **tags**（作者自打）。
- 唯一可靠入口：`tools=<工具ID>`。工具 ID 可从任意项目的 `project.project.tools[].id` 里取（先抓一个含该工具的项目，读出 id）。
- `search=ai` 只适合找「AI 题材」（大量混入卖 AI 产品的公司作品），**不等于 AI 生产**。
- 一次 21 个 AI 工具的 `tools=` 抓取 → 478 件去重（见 `collect_ai_pool.py`）。

**所以取数策略是「多领域 × 多关键词拼池子」，不是翻页。**
一次请求约 24 条 → 30 次请求能拼出 400+ 不重复作品（见 `collect_pool.py`）。

## 解析锚点：JSON 优先，语义兜底

| 页面 | 主解析源 | 结构 |
|---|---|---|
| 搜索页 | **HTML 语义锚点**（JSON 里没有列表） | 卡片 `aria-label` + `/gallery/<id>/` href + `screenReaderOnly` 文案 |
| 项目页 | 内嵌 JSON | `project.project`（modules / tools / tags / stats / covers / license / owners） |
| 个人主页 | 内嵌 JSON | `profile.user`（stats / occupation / location / teams / socialReferences） |
| 团队主页 | 内嵌 JSON | **`team.profile`**（注意：**不是** `profile.user`）+ `members`；项目列表在 `team.profile.projects` |
| moodboard | 内嵌 JSON | `collection`（items / stats / isItemsLastPage / itemsLastCursor） |

内嵌 JSON 都在 `<script type="application/json">` 里（Next.js SSR payload），取**最大的一块**即可。

**不要锚定 hash 过的 class 名**（如 `ProjectCoverNeue-root-B1h` 的 `-B1h` 是构建哈希，改版就变）。
搜索页卡片要锚在语义上：
- 卡片边界：`<div aria-label="<项目名>" class="ProjectCoverNeue-root-`
- 互动数：`screenReaderOnly` 文案 → `"2,040 views for ..."` / `"119 appreciations for ..."`（**最稳**）
- 作者：`data-axe="owners-target-size"` 容器
- 领域 ribbon：href 形如 `/galleries/<slug>/<slug>`（两段同名才是领域；`/galleries/Photoshop` 单段是工具）
- 封面：`js-cover-image`（CDN 路径含 `/projects/404/<hash>`，`404` 是尺寸档，可换 `max_1200`/`original`）

## 客户端渲染的列表：关注 / moodboard 索引（要浏览器）

**服务端只给框架、不给数据**的两类页面：

| 页面 | SSR 情况 | 拿数据的办法 |
|---|---|---|
| `/<user>/following` | 卡片是**客户端渲染**（SSR 里 19 个空壳） | 浏览器打开 → 模态框内滚动懒加载 → 取文本/结构 |
| `/<user>/moodboards` | 同上，但 **moodboard 链接是 SSR 的** | 浏览器打开，直接取 `a[href*="/moodboard/"]` |
| `/moodboard/<id>/<slug>` | ✅ **SSR 有数据** | 直接用 `moodboard` 命令，无需浏览器 |

### agent-browser 的两个硬坑

1. **必须带自定义 UA**。headless Chromium 的默认 UA 会被 Behance 判为爬虫，**所有 URL 一律 HTTP 400**（连 curl 能拿的页面也 400）。解：
   ```bash
   agent-browser open "<url>" --headers '{"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}'
   ```
2. **模态框是内层滚动容器**，`window.scrollTo` 无效。要滚所有 `scrollHeight > clientHeight + 80` 的 `div` 才触发懒加载。

### 拿关注列表的稳妥做法

不要依赖事后 eval 选择器（导航后 DOM 会变）。**用 `agent-browser read` 抓全文本 dump**，再按 `Follow` 分隔 + 统计行正则解析。
卡片文本形如：`<名字>\n<地点>\n<领域…>\n<appreciations>\n<views>\nFollow <名字>\n<username>`，
统计行规律：两个数字相邻，**第一个是 appreciations、第二个是 views**（偶有 views<appreciations 的解析歧义，标记为可疑即可，别硬修）。


每条 item 都保证有：

```
rank  id  title  author  cover  url  view  like  publish  source
```

`view` / `like` 是数字（已去千分位、`2K`→`2000`）；`publish` 是 `YYYY-MM-DD`。
Behance 专有增补：`fields[]`（领域）、`tools[]`、`tags[]`、`comments`、`owners[]`、`module_count`、`modules[]`。

拼池子时额外算两个分析字段（`collect_pool.py` 产出）：
`hits`（在几个池子里出现过 → 跨领域热度信号）、`pools`（出现在哪些池子）。

## 领域清单

`field=` 只认 Behance 的 110 个领域，值是小写（`3d art` / `character design` / `motion graphics` …），
**不是** label（`3D Art`）。完整清单可从任意搜索页内嵌 JSON 的 `creativeFields` 递归取出（脚本里已有）。

## 红线

- **只读**。不破解签名、不绕过风控、不逆向内部接口。
- 抓来的图/视频**只做研究归档**，不对外发布、不二次分发。
- **加请求间隔**（默认 1.5s），不高频轮询。
- 需要登录态（私密 moodboard / Pro Insights）时**先问用户**，别自己想办法绕。

## 下游脚本（在 vault 的 `003-Workbench/_build/`）

| 脚本 | 作用 |
|---|---|
| `collect_pool.py` | field × search 拼池子 → `data/behance-pool.json` + `.csv` |
| `collect_details.py` | 给值得深挖的项目抓详情 → `data/behance-details.json`（断点续抓） |
| `collect_ai_pool.py` | 21 个 AI 工具的 `tools=` 逐工具抓取 → `data/behance-ai-pool.json`（AI 供给盘点） |
| `collect_moodboards.py` | 先抓主页 moodboard 索引（浏览器），再逐个 `moodboard` 命令落盘 → `data/moodboards/` |
| `build_report.py` | P1：生成 `behance/*.html` 三张报告（趋势 / DCP 画像 / 自我诊断） |
| `build_phase2.py` | P2：生成 `behance/*.html` 三张报告（AI 供给 / 我的品味 / 复刻案子） |

## 常见坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 关键词不生效 | 用了 `q=` | 改用 `search=` |
| 标签筛不生效 | 用了 `user_tags=`（静默忽略） | 改用 `tools=<工具ID>` |
| 翻页没反应 | 参数被忽略 | 改用 `field=` × `search=` 拼池子 |
| `/gallery/<id>` 404 | 少了 slug | 用 `/gallery/<id>/x`（实测 200，按 id 解析） |
| 私密 moodboard 404 | 未登录，服务端判定 | 找用户要登录态，或让用户设公开 |
| 团队页解析不到 | 结构是 `team.profile` 不是 `profile.user` | 脚本已兼容，自行解析时注意 |
| 作者字段错 | 拿到了 `owners=` 的推荐位 | 只信卡片内的 `data-axe="owners-target-size"` |
| **浏览器打开 Behance 全 400** | headless Chromium 默认 UA 被判爬虫 | 传 `--headers` 自定义 Chrome UA |
| **关注/moodboard 列表抓不到** | 客户端渲染 + 模态框内层滚动 | 按上文「客户端渲染的列表」那节做 |
