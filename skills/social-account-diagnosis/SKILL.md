---
name: social-account-diagnosis
description: 只读抓取自建或对标社媒账号数据（B站 / YouTube / 小红书 / Instagram / LinkedIn / Behance），做时间线分阶段、断更检测、粉丝播放比、爆款公式反推、跨平台交叉印证与人设对照，产出账号诊断 + 行动清单。当用户说"诊断我的账号"、"看我的 B站/小红书 数据"、"账号为什么不涨"、"这个号是怎么做起来的"、"对标账号分析"、"我在各个平台写的是不是同一个人"、"我想转型但不知道做什么"时使用。全程只读，不发布、不改数据。
agent_created: true
---

# 社媒账号诊断（只读）

把"我觉得我的号不行"变成"数据说明问题在第 X 段"。核心信念：**大多数账号的问题不是内容能力，是持续性和画像错位——这两个都能用数据直接证明。**

## 一、取数

```bash
OC=~/.local/bin/opencli

# ---- B站 ----
$OC bilibili user-videos <uid> -f json 2>/dev/null > pool.json   # 投稿：title/plays/date/url
curl -s -H "User-Agent: Mozilla/5.0" -H "Referer: https://space.bilibili.com/<uid>" \
  "https://api.bilibili.com/x/relation/stat?vmid=<uid>"          # 粉丝/关注（真数据）

# ---- YouTube ----
$OC youtube channel <channel_id> -f json 2>/dev/null             # subscribers/handle/description
curl -s "https://www.youtube.com/feeds/videos.xml?channel_id=<id>"  # 最近视频；404 = 无公开视频

# ---- 小红书（需登录 creator 后台）----
$OC xiaohongshu creator-profile -f json          # ✅ 账号级：粉丝/关注/获赞/等级/bio（最稳）
$OC xiaohongshu creator-stats   -f json          # 近 7 天趋势（观看/赞/藏/评/分享/涨粉）
$OC xiaohongshu creator-notes   -f json          # ⚠️ 常返回 EMPTY_RESULT

# ---- Instagram（需登录）----
$OC instagram profile  <username> -f json        # 主页信息；返回 429 说明这条路不通，见下方兜底
$OC instagram followers <username> -f json       # 粉丝列表
$OC instagram following <username> -f json       # 关注列表

# ⭐ Instagram 兜底通道（2026-09-22 实测有效 —— 适配器 429 时用这条，别再卡住）
# 前提：用户已在 Chrome 登录 Instagram；先 $OC doctor 确认 extension connected
$OC browser ig open "https://www.instagram.com/<username>/" --window background
$OC browser ig state                             # 侧边栏能读到 "Home" = 已登录；只有登录表单 = 未登录
$OC browser ig eval "document.querySelector('meta[property=\"og:description\"]').content"
#   → "769 Followers, 3,029 Following, 72 Posts - See Instagram photos and videos from ..."
$OC browser ig eval "document.querySelector('header').innerText"
#   → 粉丝 / 关注 + 昵称 + bio 全文（人设对照必须要这条，og:description 里没有 bio）
$OC browser ig eval "[...document.querySelectorAll('a[href*=\"/p/\"], a[href*=\"/reel/\"]')].slice(0,15).map(l=>{const i=l.querySelector('img');return {href:l.getAttribute('href'),alt:i&&i.getAttribute('alt')}})"
#   → 最近 15 帖的链接 + alt（alt 含日期或 caption → 可判断更、可反推内容公式）

# ---- LinkedIn（需登录）----
$OC linkedin profile-read       -f json          # headline/About/experience/education/featured
$OC linkedin profile-analytics  -f json          # followers/connections（views 常为空）
$OC linkedin posts              -f json          # 帖子 + 互动指标
$OC linkedin profile-experience -f json          # 工作经历
```

## 二、实测坑（2026-09-19 起，2026-09-22 更新）

| 坑 | 处理 |
|---|---|
| `bilibili user-videos` 的 `likes` **恒为 0** | 解析问题 → **不采信**，如需点赞走 `opencli bilibili video <bvid>` |
| `bilibili me` 的 `followers/following` 也可能返回 0 | 不采信 → **粉丝数一律走 `x/relation/stat`** |
| 小红书 `creator-profile` → HTTP 401 | 未登录 creator 后台 → 让用户在 Chrome 登录 `creator.xiaohongshu.com` |
| 小红书 `creator-notes` → EMPTY_RESULT | 笔记列表常抓不到 → **账号级数据一律走 `creator-profile`** |
| 小红书 `user <id>` → AUTH_REQUIRED（即使 creator 已登录） | creator 后台与 www 站是**两套登录态**，要分别登 |
| **Instagram `profile` → HTTP 429（即使用户已登录也这样）** | ⭐ **别停在"让用户去登录"**。先 `$OC doctor` 确认 extension connected；再用 `browser ig open` + `eval` 走浏览器通道取 og:description / header —— **2026-09-22 实测一次成功**。适配器和浏览器是两条独立通道，前者挂了不代表没登录 |
| Instagram 登录态怎么判 | `browser ig state` 里侧边栏能读到 `Home` = 已登录；只看到登录表单 = 未登录 |
| **LinkedIn `profile-read` 的 `headline` 返回地名**（如 `"Auckland, New Zealand"`）而 `location` 是空的 | **字段错位**，真实 headline 没取到 → `about` 正文可用，headline 一律标 `[待确认]` 不要当事实用 |
| LinkedIn `profile-analytics` 的 views / impressions / search 常为空 | 只采信 followers / connections；`raw_analytics` 可能出现矛盾值（曾见 202 vs 609） |
| YouTube RSS `feeds/videos.xml` 返回 404 | 不是 ID 错，是**频道无公开视频**（空频道） |
| macOS zsh **没有 `timeout`** | 用 Bash 工具的 timeout 参数，或 `gtimeout` |
| opencli 会在 stdout 前打印 symlink / UNDICI 警告 | 落盘用 `2>/dev/null`；排错时改 `2>&1` 看错误 |
| `browser eval` 的 JS 里要用双引号属性选择器 | zsh 里会先吃掉引号 → **写成 `\\\"`（如 `meta[property=\\\"og:description\\\"]`）** |

| **`browser open` 报 `Navigation rejected`，或 `get url` 落到 `chrome-error://chromewebdata/`** | ⭐ **先原样重试一次再下结论。** 境外站（Instagram / LinkedIn）首次导航常失败，第二次通常就成（2026-10-03 实测：IG 第一次超时 → 第二次成功）。判据：`curl -o /dev/null -w "%{http_code}" --max-time 15 <url>` 返回 **200 但耗时 9–15s** = **网络通、站点慢**，不是断网 |
| `browser <s> bind` 可能绑到 `about:blank` | bind 绑的是"当前窗口/标签"，未必是用户打开的那页 → **bind 后必须先 `get url` 确认落到哪**；落错了让用户把目标标签切到前台再 bind |
| 想拿 IG 帖子发布日期 → 别走 `instagram.com/p/<短码>/embed/captioned/` | 2026-10-03 实测该接口在本机**空返回 / 超时**。日期一律读本地归档的 `post_date`（gallery-dl 写的 sidecar `.json`）——**先查本地，别重新抓** |

**铁律**：抓不到就说抓不到，标注 `[待补]`，绝不编造粉丝数、播放量、互动数据。

## 三、诊断五步

1. **分阶段**：按标题主题把投稿切成阶段（工具/教程 vs 生活/vlog），各算均播。**找断崖。**
2. **断更检测**：相邻投稿间隔 > 3 个月的标出来。断更常常比"发得差"更致命，且会被忽略。
3. **粉丝播放比**：`播放 / 粉丝 < 10%` → 内容与粉丝画像错位（不是平台不推，是老粉不点）。
4. **公式反推**：从 Top 3 标题里提炼反复出现的结构（`工具名 + 产出 + 形式`）。**用户验证过的公式比他没做过的选题值钱。**
5. **跨平台交叉印证**：每个平台独立算，看是否指向同一个病——
   - 供给不足（断更 / 作品少 / 空号）
   - 曝光不足（效率高但观看低）
   - 画像错位（播放/粉丝比低）
6. **人设对照**：把各平台的 bio / 简介 / About **并排**列出来。
   **多平台写着多个人 = 定位分裂**，这比断更更基础——观众认知不成立，涨粉和商单都无从谈起。
   - 判据：一句话能否说清「这人替观众解决什么」？
   - 典型症状：专业身份只写在 LinkedIn / 作品集 / Instagram，中文平台写的却是情绪自述（迷茫、转码、斜杠青年、我不确定要做什么）。
   - ⭐ **先按语言分组，再下结论**：常见形态是「英文侧写对了、中文侧写错了」，而不是每平台各错各的。
     若是这种，**结论要从"重新想定位"降级为"把已经写对的那版翻成中文"**——工作量和心理成本差一个量级，而且更好执行。
     （2026-09-22 实例：6 个平台里 LinkedIn + Instagram 都写对了，小红书 / YouTube / B站 都写错了。）
7. **受众资产盘点**（用户同时在做 IP / 第二品牌 / 新产品时必做）：
   把「个人号粉丝」与「目标品牌号的粉丝」**分开数**。常见发现是：个人号已有几千几万粉，而新品牌**零分发**。
   → 那么正确顺序是「**先修个人号 = 先修分发渠道**」，而不是给新品牌从零起号——0→1 比转化存量贵得多。
   → 问一句即可：**「你已经有多少人愿意看你？这些人现在能看到你的新产品吗？」**


## 四、输出格式

1. **一句话结论**（先给定性，别先给数据）
2. **数据表**（各平台：粉丝数 / 关注 / 最好的一条 / 核心信号）
3. **人设对照表**（各平台 bio 并排 —— 常常比数据更说明问题；**先按语言分组**）
4. **受众资产表**（若用户在做 IP / 第二品牌：个人号粉丝 vs 品牌号粉丝，八成会发现后者是 0）
5. **交叉印证**（各平台分别诊断 → 合起来指向什么）
6. **诊断清单**（按投入产出比排序，不是按重要性；**人设统一通常排第一**）
7. **「如果只做一件事」**（一个动作，说清为什么是它）
8. **待补**（没取到的数据如实列出 + 需要用户做什么）

## 五、常青结论（写给创作者）

- 从 Top 3 反推出的公式，通常和用户"想转型的方向"不冲突——**转型 ≠ 换赛道，多半是"把公式里的工具换掉"**。
- 情绪向内容（内耗、碎碎念、"寻找小伙伴"）在中腰部账号上几乎从不开花：**那是创作者的需求，不是观众的需求。**
- 老粉不是负资产：关注"这人会用工具做东西"的人，对工具换代是宽容的。
- ⭐ **"人设分裂"经常不是想不出来，而是想对了、但只写在了英文平台。** 先按语言分组核对，再决定是"重想定位"还是"翻译文案"——后者便宜一个量级。
- ⭐ **用户已经跑通的公式，常常正活在他自己的另一个平台上。** 把他各平台的内容句式横向比一遍，常见发现是"他在 A 平台一直用对，回 B 平台却丢了"。
- ⭐ **适配器失败 ≠ 账号没登录。** `browser` 通道是通用兜底层，别因为一个 CLI 报错就判定某平台取不到数、让用户白跑一趟去登录。
- **存量受众是分发资产，不是历史包袱。** 做新 IP / 新产品前先算一遍"存量受众能不能看见"，再决定要不要从零起号。

## 六、对标合集拆解（YouTube Playlist / B站合集）

用户丢来一个「我想做类似这样的系列」的合集链接时 —— **别只夸它好，要拆出它的结构和空位。**

```bash
yt-dlp --flat-playlist --dump-json --no-warnings "<playlist_url>" 2>/dev/null \
  | ~/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -c "
import sys, json
for l in sys.stdin:
    try: d = json.loads(l)
    except: continue
    print(d.get('playlist_index'), '|', d.get('title'), '|', d.get('duration'), '|', d.get('view_count'))"
```
`--flat-playlist` = **零下载、秒出**。（`view_count` 可能是约数 → 标 `[yt-dlp]`。）

**要拆的三件事：**
1. **时长带** —— 全部落在什么区间？（实测样本：11 集全在 293–654s，即 5–11 分钟）
2. **标题公式** —— `How to X` / `N Advanced X` / `Foundations of X` / `X Explained`…
3. ⭐ **播放分布** —— **按「概念集 vs 工具/实现集」分组比**。实测样本：概念集 457K vs 工具集 14K，**差 32 倍**。
   → 可复用结论：**"讲清一件所有人都会遇到的事" > "教一个具体工具怎么用"**。
   ⚠️ 但必须标 `[观察-非因果]` —— 头部那条可能吃了算法累积或官方推荐位。

**给建议时的关键动作：不要建议用户照抄题材，要指出"哪个位置是空的"。**
判据：**这个合集里，哪些主题是「官方/大厂不会做、但这个用户真的做过」的？** —— 那就是他的位置。
（实例：官方课教「ADK 应该怎么配」，用户的空位是「实际会怎么翻车」——依赖、环境、成本、归档。）

⚠️ 同时检查**术语陷阱**：用户说的"基础"可能是「入门教程」（红海、无护城河），也可能是「别人不讲的地基层」（供给极薄）。
先问清是哪一种再动手 —— 判据：**这个选题"搜索一下就有答案"吗？有 = 前者，不做。**

