---
name: studio-site-teardown
description: 把某个同行 / 工作室 / 创作者的站（或行业目录条目、Behance 主页）**只读**抓下来，反推它的「定位话术 + 站点结构 + 真实体量」，结论落进 `Wiki/Studio-参考库.md`。当 Seth 说「看看这个人的站」「这个工作室怎么弄的」「我后面要做类似的」「这个对标怎么样」，或丢来一个同行/公司链接时使用。
agent_created: true
---

# 同行站点拆解（studio site teardown）

**目标**：不是"抄一个站"，是拿到三样东西 —— ① **他的话术**（对外怎么说）② **他的结构**（页面怎么排）③ **他的实况**（真有多少量）。
**产物**：`Wiki/Studio-参考库.md` 新增一节（⛔ 不新建页，扩写现成页）。

---

## 第 0 步：判平台（决定后面用什么工具）

```bash
opencli browser <s> open "<url>" && opencli browser <s> eval "(()=>{const g=document.querySelector('meta[name=generator]');return JSON.stringify({gen:g&&g.content,html:document.documentElement.outerHTML.slice(0,2000)})})()"
```

| 判据 | 平台 |
|---|---|
| `meta[generator]` = "Wix.com Website Builder" · `static.parastorage.com` · `wixstatic.com` | **Wix** |
| `squarespace-cdn.com` + `collection-<id>` body | **Squarespace** |
| `cdn.membershipworks.com` | **MembershipWorks**（行业目录，如 MDGA / PASC） |
| `framerusercontent.com` | **Framer** |
| `webflow.com` / `assets.website-files.com` | **Webflow** |

> ⭐ **Wix / Squarespace 站 = 免代码**，本身就说明"他没在这上面花工程时间，钱花在内容与话术上" —— 这本身就是结论。

---

## 第 1 步：抓正文

**hash 路由站点**（`#!biz/id/…`）→ `#` 后面**不发给服务器**，WebFetch 抓不到 → **必须浏览器渲染后再读**。

```bash
# 静态站 / 营销页：最省
opencli browser <s> eval "(()=>JSON.stringify({title:document.title,text:document.body.innerText.slice(0,7000)}))()"

# 长文 / 文章页：走 extract（有分块游标）
opencli browser <s> extract --chunk-size 8000
```

**一页一页过**（导航里的每一条都读一遍，别只读首页）：
`/` `/work` `/capabilities` 或 `/services` `/about` `/<AI 页>` `/contact`

> ⭐ **SPA + 懒加载时 `extract` 会拿到空壳**（Wix 视频 `video` 元素无 `src`）→ 直接 `eval` 读 `innerText`。
> 真视频地址在 `<a href>` 里（`video.wixstatic.com/.../mp4/file.mp4`）。

---

## 第 2 步：抓结构

```bash
# 全站导航 + 外链（社媒）+ 资源
opencli browser <s> eval "(()=>{const a=[...document.querySelectorAll('a')].map(x=>x.getAttribute('href')).filter(Boolean);return JSON.stringify([...new Set(a)])})()"
```

要记的点：
- **导航条目** = 他把什么当卖点（如 `AI STUDIO` / `NZ PRODUCTION` 直接开成一级页）
- **作品页的形态**：逐案 case-study？还是全屏视频轮播？（后者 = 低维护，靠片子说话）
- **类别标签** = 他的信誉阶梯（COMMERCIAL / PRODUCT FILM / VFX / BEHIND THE SCENE / **AI COMMERCIAL**）
- **联系表单字段**：有没有 **预算 / 周期 / 项目类型** → 有 = 资格筛选，不是纯收信
- **没有的东西**同样重要（无博客 / 无 case-study / 无价格）

---

## 第 3 步：抓体量（"他真有量吗"）

```bash
opencli youtube channel "@<handle>" -f json     # 订阅数 + 近期视频 + 播放量
opencli instagram user <handle>                 # 可选，需已登录
```

> ⭐ **关键区分**：**门面（客户看的站）≠ 粉丝引擎（涨粉的号）**。
> 站做得漂亮但 YouTube 20 订阅 → 他是**接单型**工作室，不是**建受众型**创作者。
> 这两条路别混着用（见 `Wiki/Studio-参考库.md` §八 第 5 条）。

---

## 第 4 步：落库

1. **`Wiki/Studio-参考库.md` 新增一节**（⛔ 不新建页）。表格列：身份一句话 / 公司 / 网站怎么搭的 / 类别阶梯 / 页面结构 / **他没有的东西** / 社媒实况 / 客户长相。再附「**他的话术原话**」+「**可迁移的 N 条**」。
2. **`Wiki/Studio-定位与作品集.md` §四 参考坐标** 加一行指针。
3. **`000-你给我的.md` 流向表** 加一行（链接的默认落点）。
4. `Daily/<今天>.md` + `.workbuddy/memory/<今天>.md` 各记一条。

---

## 坑（踩过的）

- ⚠️ **hash 路由 `/.../#!biz/id/xxx`** → WebFetch 抓不到，必须 `opencli browser`。
- ⚠️ **行业目录条目 id 会长得像**：Ashton 的 `…0454d2` vs Seth 自己的 `…045579` 只差两位 → **别抓成自己**，核对页内姓名。
- ⚠️ **`2>/dev/null` 会吃掉 opencli 的错误** → 调试时别加。
- ⚠️ Wix 站 `video` 元素无 `src`（懒加载），别据此判断"没视频"。
- ⚠️ **对外口径**：写结论时按实际 —— 站上写的是他自己说的，别替它加码。
