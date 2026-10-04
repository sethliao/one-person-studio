---
name: behance-case-deck
description: 把一个 IP / 项目做成「能直接发上 Behance 的完整案子」—— 20 张 1920×1080 看板 + 可播的 Still/Animation 模块 + 案例页 HTML + 上传包。当用户说"把 X 做成一个 Behance 案子"、"给 X 做作品集"、"照着别人的案例做一版"、"做一个完整 case"、"帮我排版一套陈列图"时使用。也用于生成任何 1920×1080 的提案 deck / 项目陈列板。
agent_created: true
---

# Behance 完整案子（看板 + 案例页）

把项目变成 **一串等宽 module**，不是一个长图。这是 Behance 上「案子感」的来源。
参考拆解见 vault `Wiki/Research/Behance-完整案子写法-2026-09.md`。

## 铁律

1. **动手前先看参考的画面**。Behance 服务端渲染，`WebFetch` 抓不到，必须走
   `behance-research` 的 `behance_fetch.py project <id>`。**标题 / 封面 / tags 都不算数。**
2. **图片尺寸档要换**：`/project_modules/disp/` 只有 600px 宽；换 **`/fs/`** 才是原尺寸。
   `max_1200` / `original` / `opt` 全是 302 死链。
3. **Still 与 Animation 必须分开成节，且挨着放。** 静帧证明造型，动态证明它会动。
   只放静帧 = 画集；只放视频 = 看不清细节。
4. **未完成 / 未发布的物料必须标注** `in production` / `concept`，别让人当成已商业落地。
5. **AI 出图的水印要裁掉**（内置出图右下角有「AI生成」，裁掉底部 ~64px）。

## 标准骨架（20 页）

```
00 封面                     11 ─ 章节三分隔
01 ─ 章节一分隔              12 结构（分集 / 模块 / 交付清单）
02 概念（+ 一句大写核心发问）   13 分镜 / 流程拆解
03 世界观 / 场景             14 Still（静帧网格）
04 受众 / 为什么值得做         15 Animation（可播视频卡）
05 设计主体（角色 / 产品）      16 ─ 章节四分隔
06 阵容 / 系统拆解            17 落地应用 A
07 ─ 章节二分隔              18 落地应用 B（社媒 / 线下）
08 情绪板（纯拼贴，不写字）      19 Credits + Tools + Tags
09 色彩系统
10 Logo & 图形元件
```

判据只有三条：**① 每页一个观点；② 每 3–4 页插一张分隔页；③ 结尾必须有 Credits。**

## 流程

### 第 1 步 · 定内容源
- 先盘点**已有真实素材**（角色定稿、成片、关键帧）—— 能不用 AI 生成就不用。
- 需要补的主视觉（封面 / 氛围图 / 白底角色图）再走内置出图。
  ⚠️ 内置出图 **每张约 5–10 credits**，动手前必须报数等点头。
- 白底图抠透明：`alpha = clip((252 - lum)/26, 0, 1)`，`alpha<0.23 → 0`，再 `crop(bbox)`。

### 第 2 步 · 渲染看板
```bash
P=~/.workbuddy/binaries/python/envs/default/bin/python
cd ~/Documents/hermes_vault_clean/003-Workbench/_build
$P build_momo_case.py [slug...]     # 不带参数 = 全出；带参数 = 只出匹配的
$P build_momo_case_page.py          # 出案例页 HTML（两处落地）
```
- `build_momo_case.py` 里 `BOARDS` 决定页序；每页一个 `bXX()` 函数；改文案直接改函数体。
- 产出 `Assets/momo-case/boards/<编号>-<slug>.png|jpg`（1920×1080）。
- **这两个脚本就是模板** —— 换 IP 时复制一份，改 `BOARDS` / 文案 / 素材路径即可，
  渲染原语（`paper_bg` / `cover` / `paste_round` / `paste_rgba` / `wrap` / `tracked` /
  `chip` / `lantern` / `star_uni` / `paw` / `play` / `chrome` / `section_list`）不用重写。

### 第 3 步 · 出案例页 HTML
`build_momo_case_page.py` 里 `MODULES` / `EPISODES` / `CREDITS` / `KIT` 是内容源。
同时输出两份：`Assets/<案名>/index.html`（自包含，可打包）+ `003-Workbench/behance/<案名>.html`（工作台入口）。

### 第 4 步 · 质检（别跳过）
```bash
# 断链 + markdown 星号残留
python -c "..."   # 见脚本尾部校验逻辑
# 浏览器实测（视频 readyState 必须 = 4）
cd Assets/<案名> && agent-browser open "file://$PWD/index.html"
agent-browser eval 'JSON.stringify([...document.querySelectorAll("video")].map(v=>({rs:v.readyState,dur:Math.round(v.duration*10)/10,w:v.videoWidth})))'
agent-browser close
```
⚠️ `loading="lazy"` 的图，先 `eval` 把 `loading` 设成 `eager` 再看 `naturalWidth`。

### 第 5 步 · 归档
- 拆解笔记 → `Wiki/Research/Behance-完整案子写法-YYYY-MM.md`
- 工作台卡片 → `003-Workbench/behance/index.html`（nav + card + 报告计数，三处都要改）

## ⚠️ 工程坑（都踩过）

| 坑 | 症状 | 解法 |
|---|---|---|
| **Pillow text 参数顺序** | `TypeError: color must be int or tuple` | 签名是 `text(xy, text, fill, font)`，不是 `(xy, text, font, fill)`。脚本顶部已加纠偏 shim |
| **CJK 字体选错 face** | 少了 glyph、出现怪字符、标点单独占一行 | `Hiragino Sans GB.ttc` 用 **index 0**；index 1 是 Interface 子集 |
| **折行把标点甩到行首** | 行首孤零零一个「」」 | 维护 `NO_LEAD` 集合，命中时不换行 |
| **`grain()` 模式不匹配** | `ValueError: images do not match` | 噪声图 `.convert(img.mode)`，别硬写 RGB |
| **RGBA figure 上画透明色** | 月牙变黑饼 / 底部露出奇怪色块 | 要挖空就走 `mask` 粘贴，别用 `fill=(0,0,0,0)` |
| **元素压到页脚** | 网格最后一行被页脚线切掉 | 页脚线在 `y=H-78`。排版前先算：`行数 × (高+间距) + 起点 < H-118` |
| **CN 标题用了拉丁字体** | 中文变 □□ tofu | 中英混排拆两次 `d.text`，CN 用 `cn`/`cnb` 字体 |
| **出图水印** | 右下角「AI生成」 | 裁掉底部 64px（对 1536×1024 的图安全） |
| **GIF 代替视频** | 画质崩、单张 8MB 上限 | Behance 用视频模块，H.264，≤ 60s |

## 发布到 Behance 的实操（写进页面的「上传包」一节）

- Cover 用第 00 张；modules 按编号顺序全传（Behance 按上传顺序排）。
- 标题：`主名 — 一句话定位`；简介写**英文**（Behance 以英文分发为主）。
- **Tools 栏是固定清单**，勾最接近的即可，真实管线写在 Credits 里，别为了填而填。
- Tags 8 个左右：题材 + 技法 + 媒介。

## 已落地案例

| 案 | 看板 | 案例页 | 备注 |
|---|---|---|---|
| 熊猫莫莫 · Character IP Case Study | `Assets/momo-case/boards/` (20 张) | `Assets/momo-case/index.html` | 含 4 条可播成片 + 上传包 |
