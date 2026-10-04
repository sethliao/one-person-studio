---
name: social-media-archive
description: 把 Seth 自己在各平台发的 / 提到他的帖子（Instagram / B站 / LinkedIn / 小红书 …）连同媒体文件下载到本地 vault 归档，并维护一份可检索的索引。当他说「把这些链接抓下来」「我的 post 都下载下来」「存到 vault」「给我的社交媒体做个检索」「归档我的作品」时使用。
agent_created: true
---

# 社媒素材归档

**回答一个问题：他自己发过的东西，怎么安全地落到本地、并且以后能找回来？**
（跟 `social-account-diagnosis` 分工：那个做**数据诊断**，这个做**媒体留底**。）

产物落点固定：`Assets/Seth-社媒档案/<平台>/` · 索引写进 `Wiki/Seth-账号矩阵.md`。

---

## 第 0 步：先查库，别重抓

```bash
fd . ~/Documents/hermes_vault_clean/Assets/Seth-社媒档案
rg -l "<短码或关键词>" ~/Documents/hermes_vault_clean
```

已在 `Wiki/Seth-账号矩阵.md` / `Seth-跨平台账号诊断-2026-09.md` 里的账号级数据（粉丝数、帖子列表）**不要重抓**。

---

## 各平台通道（实测结论，2026-10-03）

| 平台 | 下媒体 | 读文本 | 备注 |
|---|---|---|---|
| **Instagram** | `opencli instagram download <url> --path <dir>` | `opencli web read --url <url>` | ⚠️ **本机 curl 直连不通，只能走 opencli** |
| **B站** | `yt-dlp` | `opencli web read` | 1080P 高码率需大会员 cookies |
| **LinkedIn** | ✅ **`media.licdn.com` 图片可 curl 直连** | `opencli web read` 读单帖 | `opencli linkedin posts` 只对他人的活动页有效 |
| **小红书 / 抖音 / 微博** | 未验证 | `opencli web read`（需登录） | 见 `000-线索引.md` |

### 配方

```bash
# ① 通用：任意页面（含登录后）→ Markdown，零 token
opencli --profile hegpkpwu web read --url "<URL>" --stdout true -f md

# ② Instagram 图文 / reel → 本地
opencli instagram download "https://www.instagram.com/p/<短码>/" --path /tmp/ig-archive

# ③ B站视频
yt-dlp -f "bv*+ba/b" --merge-output-format mp4 -o "BV<id>.%(ext)s" "https://www.bilibili.com/video/BV<id>/"
yt-dlp --skip-download --print "%(title)s|%(duration)s|%(upload_date)s|%(view_count)s" "<URL>"   # 只要元数据

# ④ LinkedIn 图片（从 web read 输出里捡 media.licdn.com 直链）
curl -s -o li-01.jpg "<直链>"
```

---

## ⚠️ 六个坑（都实测撞过，别重踩）

1. **`Navigation rejected` 不等于"这个站抓不到"。** 两个诱因：
   ① **daemon 版本陈旧**（CLI 升级了 daemon 没升）→ `opencli doctor` 会报 stale → `opencli daemon restart`；
   ② **连续高频请求把浏览器通道打满** —— 之后连 `web read` 都会一起失败。
   → **纪律：开抓前先 `opencli doctor`；每连续抓 3–4 个目标就 restart 一次，不要硬刷。**
2. **`instagram download` 是逐张 fetch，会部分成功。** 会报 `Failed to download xx_03.jpg: fetch failed` 但**前几张已经在磁盘上了**。
   → **报 error 后第一动作是 `ls` 目标目录数文件**，不要以为整条失败。个别图片的 CDN 链接可能已失效，重试也回不来。
3. **改 LinkedIn 图片 URL 路径会 403。** 想把 `feedshare-shrink_480/800` 换成 `feedshare-image-high-res` 取高清 → 签名校验直接拒（返回 22 字节错误体）。
   → **只能用页面给的原 URL 原样下。** 已在磁盘上的假图要 `rm` 掉（`file` 一看就是 ASCII text）。
4. **归档媒体 ≠ 可以随便发。** `Assets/` 里的东西含**他人面孔与第三方内容**（队友、活动现场、品牌 KV）。
   → 只做本地留底；**任何对外用途（发帖 / 送人 / 放作品集）先过 Seth**。
5. **报错信息会骗人：`Failed to download xx_03.jpg` ≠ 整条失败。**
   2026-10-03 实测：`DHDgcBvPBVQ` 报"第 3 张 fetch failed"，但**那条帖只有 2 张图、且两张都已落盘**。
   → **第一动作永远是 `ls` 目标目录**；要真实失败点用 `--trace retain-on-failure`。
   → 同理，**别在清理命令里用通配符扫 vault 路径** —— 我曾在一次清理里把已归档的图 `rm` 掉了（路径写成了 vault 而不是 /tmp）。
     **删任何东西前先确认路径指向 temp 还是 vault。**
6. **拿"新鲜直链"用 `eval`，但拿到也未必能下。** 帖子页面的图不在简单的 `img.src` 里，用这条精确捞主图
   （靠 URL 里 `t51.75761` / `CAROUSEL_ITEM` 特征区分主图与头像）：

   ```bash
   opencli <profile> browser <session> open "https://www.instagram.com/p/<短码>/"
   opencli <profile> browser <session> eval \
     'JSON.stringify([...new Set(Array.from(document.querySelectorAll("img")).map(i=>i.src).filter(s=>s.includes("t51.75761")||decodeURIComponent(s).includes("CAROUSEL_ITEM")))])'
   ```

   ⚠️ 但 **`instagram.ftpe8-*.fna.fbcdn.net` 在本机 curl 仍然超时**（用户开代理也没覆盖这个子域）。
   → **图片落盘只能走 opencli（Chrome 通道）。`eval` 拿直链的意义仅限于"确认有几张图 / 存档链接"。**

---

## Instagram 主页抓取的正确姿势（2026-10-03 实测 · 只拿到 22/72 帖的教训）

```bash
# ① 先体检 + 读技能地图（⚠️ 我这次跳过了这两步，白试了十几轮）
opencli doctor
# 并加载 skill：opencli-usage（顶层地图）→ opencli-browser（驱动细节）

# ② 首选 bind：绑他本人已经打开、能正常访问的标签页
#    —— 这一步直接解决 Navigation rejected / ERR_CONNECTION_CLOSED
opencli <profile> browser <session> bind

# ③ 主力命令：把页面转 markdown —— ⭐ 每条帖子的 caption 全文都在里面
opencli <profile> browser <session> extract

# ④ 图片落盘走适配器
opencli instagram download "<帖子URL>" --path <dir>
```

**⚠️ 五个实测限制：**

1. **`--window background` 时 IG 不触发懒加载** → 必须 `--window foreground`。
   （用户原话：「滚动用不了是因为没有调到前台，所以没有加载」）
2. **IG 用内层 div 滚动**，不是 window。实测容器 **clientHeight 6522px / scrollHeight 7178px**。
   `window.scrollBy` / `el.scrollTop=` / `WheelEvent` 派发 / `browser scroll down` / `keys End`
   —— **五种全试过，帖子数卡在 22 不动**。
3. **页面内 fetch IG API（`/api/v1/users/web_profile_info/`）被重定向回 HTML**（返回 `<!DOCTYPE`，不是 JSON）。
   带 `x-ig-app-id` + `credentials:"include"` 也不行。
4. **适配器与 browser session 不能同时用** —— session 占着标签时，`instagram user` / `profile` /
   `web read` 一律 `Navigation rejected`。要用适配器就先 `browser <session> close`。
5. **翻不动时的正解**：既然你 `bind` 的是**他本人的标签页**，**让他自己滚**就行 ——
   他滚完你再 `extract`，内容就出来了。比自己跟 IG 的虚拟滚动搏斗见效快得多。

> 🔀 **翻不动全量时的正解：直接换 `gallery-dl`（见下节）** —— 不走浏览器 DOM，走 API + cookie，一次拿全。

---

## ⭐⭐ 全量归档的正解：`gallery-dl` + Chrome cookie（2026-10-03 实测通过）

```bash
GDL=~/.workbuddy/binaries/python/envs/default/bin/gallery-dl
$GDL --cookies-from-browser chrome -d <目标目录> --write-metadata "https://www.instagram.com/<用户名>/"
```

**为什么这是正解：**

- ✅ **实测通** —— 从 Chrome 提取 **3613 个 cookie**，直接下载成功，绕开所有浏览器自动化限制。
- ✅ **一次拿到「正文 + 时间 + 点赞 + 链接」** —— 每条目旁的 `.json` sidecar 字段：
  `description`(=caption) · `post_date` · `date` · `likes` · `tags` · `post_url` · `post_shortcode` · `type` · `username`
  → **不用再逐帖 extract，也不用跟懒加载搏斗。**
- ✅ **不需要密码** —— cookie 走的是浏览器登录态。⛔ **绝不要用 `--password`**（会进 shell history 和进程列表）。

**对比：**

| 工具 | 结果 |
|---|---|
| `instaloader`（匿名） | ❌ 实测 **0 文件**，IG 直接挡 |
| `instaloader`（登录） | 可行但有封号风险，且需交互输密码 |
| **`gallery-dl --cookies-from-browser chrome`** | ✅ **推荐** |
| `opencli browser`（extract/滚动） | 🟡 只能拿首屏 ~20-42 帖，翻不动分页 |

**⚠️ 必读的风险提示：**

> `gallery-dl` / `instaloader` 都是**用他自己账号的 session** 去抓，Instagram 可能限流甚至封号。
> instaloader 官方文档原话：*"Usage may lead to the loss of the Instagram account."*
> → **必须用户明确要求才用**。我应做的缓解：① 用 cookie 不用密码 ② 不抓 stories/highlights（更敏感）③ 跑一次就停，别反复。
> → **长期归档应迁到 Instagram 官方「下载你的信息」导出**（设置 → 你的活动 → 下载信息）：零风险、100% 完整、含 Memories。

> 🔀 Seth 另装了 **BrowserSkill（Tencent）**，本 skill 尚未验证。

---

## 归档时的规矩

- **目录按平台 + 帖子 ID 分**：`instagram/<短码>/` · `bilibili/<BV号>.mp4` · `linkedin/<post-id>/`
- **文本也要存**：LinkedIn 这类存成 `<post-id>/post.md`（frontmatter 记 platform / post_id / author / posted_at / result / url / archived）
- **第三方提及要标出来**：如果不是 Seth 本人发的（如队友发的获奖帖），frontmatter 里写明 `author` 与"⚠️ 这条不是本人发的"
- **索引写进 `Wiki/Seth-账号矩阵.md` 的「媒体归档」节**（不要新建页面 —— 库内约定：先扩写现成页）
- ⚠️ **反编造**：索引里的日期、播放数、点赞数一律从命令输出复制，**不凭印象手写**

---

## 收工检查

```bash
find ~/Documents/hermes_vault_clean/Assets/Seth-社媒档案 -type f | sort
du -sh ~/Documents/hermes_vault_clean/Assets/Seth-社媒档案
```

- [ ] 每个目标：成功几张 / 失败几张，**逐个写清**（别笼统说"抓到了"）
- [ ] `README.md` 的「待补」节更新失败项
- [ ] 新确认的事实（合作厂商名、赛事全名）回写 `Wiki/Seth-账号矩阵.md`
