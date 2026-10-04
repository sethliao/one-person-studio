---
name: behance-replicate-run
description: 用本地 DramaClaw×G-Labs 管线（gateway :8790 / 或直连 G-Labs :8765）把一条 Behance 参考片「跑通」成自己的片子 —— 看图定调 → spec 出图/出片 → 合成 → 出工作台看板页。也用于给「AI 能不能替我做角色 / 产品 / 某种画风」这类问题做 A/B 实测。当用户说"跑通一条"、"复刻这个"、"试这个参考"、"实测一下还原度"、"跑一下这个画风"、"帮我做条片子看看管线行不行"时使用。
agent_created: true
---

# Behance 复刻实测（跑通一条）

把一个参考变成一条能播的片子，并**如实记录它哪里不行**。
取数另见 skill `behance-research`；gateway 端点配方见 skill `drama-claw-hermes`。

## 铁律（四条都付过学费，别重蹈）

1. **动手前必须有画面级证据。** 项目详情（`tools` / `tags` / `modules`）+ **至少 2 张图**。
   - 第 1 课（Emanation）：没看图 → **方向**写错 prompt，白烧额度。
   - 第 2 课（Mectron）：只看标题 → **类型**判错（标成「产品片」，实际是牙科品牌吉祥物动画短片）。
   - **标题和封面都不算数。** 类型判错 → 技法、成本、风险点全错。
2. **有参考图 / 没参考图是两个质量档。** 做还原类（角色、产品、建筑）**必须**带 ref，否则模型只是在猜。
3. **⭐ prompt 必须与参考图互相印证，不能互相打架。**（第 3 课，最贵的一课）
   - Mectron 那轮：作者 tags 写 `Dinosaur` → 我 prompt 写「blue dinosaur」，
     但画面里其实是一只**巨型牙齿**。两个信号在拉扯 → **一半的漂移是我造成的，不是模型的锅**。
   - **做法：把参考图里每个特征逐条列出来，prompt 只写你亲眼看到的。**
     名字 / tags / 标题 / 作者自述都可能误导 —— **只有画面算数。**
4. **分清任务性质，再决定期望值。**
   **风格迁移（「像那一类」）AI 很行；角色还原（「就是那一个」）不行。**
5. **⭐ 有角色就必须挂角色参考图 —— 一条都不能省。** 背影镜尤其容易漏，
   而漏了就会凭空长出螺旋发、脖子和新布景（C1 镜 4 实况）。
   另外：**场景 prompt 要写死相机语言**（`camera is inside the set, we never see the outside walls`），
   否则同一句 prompt 会在不同镜次生出不同机位，镜与镜之间「跳世界」。

## 标准流程

### 第 0 步 · 看图（不可跳过）

```bash
P=~/.workbuddy/binaries/python/versions/3.13.12/bin/python3
S=~/.workbuddy/skills/behance-research/scripts/behance_fetch.py
$P $S project <id> -o <data>/proj.json       # 拿 tools/tags/modules
```
- `modules[].image` 是图片直链（`.png`/`.gif`），`modules[].video` 常为 null。
- **GIF = 动画**：`ffmpeg -i x.gif -vf "select=eq(n\,0)" -frames:v 1 out.png` 抽帧看内容。
- 把参考图下载到 `003-Workbench/media/refs/<项目>/`，规整成 `original/`（原件）+ `frames/`（抽帧）+ 精选几张。
- **用 contact sheet 一次看全**（省 Read 次数）：ffmpeg `scale+pad` 后 `xstack` 拼图。
  ⚠️ 本机 ffmpeg **没有 `drawtext`**（无 libfreetype），别用它标注。
  ⚠️ **zsh 不对未加引号的变量分词** —— 循环里别写 `for spec in "a 1.0" ...; do set -- $spec`，用 Python 写。

### 第 1 步 · 定参考资产

- 需要还原的「具体物体」（角色/产品）→ 从参考帧 **裁剪一张干净的本体图** 当 ref：
  `ffmpeg -i frame.png -vf "crop=W:H:X:Y,scale=..." ref.png`
- **读一眼裁剪结果**，确认特征（颜色 / 轮廓 / 材质）都在。

### 第 2 步 · 出图（`gen_frames.py`，支持 refs）

```bash
cd 003-Workbench/_build
$P gen_frames.py specs/<x>.json     # 幂等：有产物就跳过
```
- ⭐ **`/v1/images/generations` 同样吃 `reference_images`** —— 图生图可用。
- ref 传递按后端分：`--backend native`（**默认**）走 **base64，不碰磁盘 → vault 里的图可直接用**；
  `--backend gateway` 无 base64 通道，脚本会先复制到 `~/.hermes/drama-gateway/media/` 再提交
  （绕开 G-Labs 的 TCC 限制；ref 直接放 `~/Documents` 可能报 `UPLOAD_ERROR Operation not permitted`）。
- 带 ref 实测 **36–44s/张**，纯文生 **~40s/张**。

**做 A/B 实测时**：两组 prompt **一字不改**，唯一变量是 ref。否则测不出结论。

### 第 3 步 · 出片（`gen_clips.py`，支持 per-clip duration）

```bash
$P gen_clips.py specs/<x>.json
```
- `duration` 只认 **4/6/8/10**；`resolution` 只认 360p/720p/1080p/4K。
- **想省额度就用 `"resolution": "360p"`**（Seth 常用）。实测 640×360 / 24fps，出片 **48–52s/条**。
- **有 reference_images → 自动走 Omni Flash `components` 模式**；**不锁首帧**（Seth 的铁律）。
- 实测 **51–59s/条**（6s/720p）。

### 第 4 步 · 合成（`assemble_reel.py`）

```bash
$P assemble_reel.py specs/<x>.json
```
- 总时长 = `sum(len) - xfade × (n-1)`，脚本自算。
- **⚠️ `duration` 被限死在 4/6/8/10**（`gen_clips.py`），所以「凑整」实际是
  **先挑 xfade 让 `目标 + xfade×(n-1)` 落在可用组合上**，而不是去改片段长度。
  - 例：**5 镜要正好 30.0s** → 片段和需 `30 + xfade×4`。
    `xfade=1.0` → 34 ✅ = **6+6+6+8+8**（实测可行，成片正好 30.000s）
    `xfade=0.5` → 32 ✅ = **6+6+6+6+8**（更省一点，但溶解更急）
  - 例：**5 镜 3×6s + 2×8s** → 34 − 0.8×4 = **30.8s**（不是 30.0，别记错）
- `drone: null` → 不加低频底噪。**品牌片/节奏片应该关掉**，氛围片才加。
- 可选 **`scale`** 键（默认 `1280:720`）。**源是 360p 就写 `"scale": "640:360"`**，别让它假装成 720p。
- 音频用 ffmpeg 合成正弦 + loudnorm，**零花费**（`/v1/audio/speech` 只有 TTS，没有音乐生成）。

### 第 4.5 步 · 想加「定格 / 顿帧」质感？后期白嫖，别求模型

```bash
ffmpeg -i reel.mp4 -vf "fps=12" -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
       -c:a copy -movflags +faststart reel-12fps.mp4
```
- **零消耗、可控、可反复试。** 定格动画真正的节奏是 12fps。
- prompt 里写 `frame-by-frame stepping, like 12fps puppet animation` 也有效（实测室内镜
  **53% 帧为静止帧**、瞬时跳变 16.1，确有 stepping 特征），但**不稳定，别当依赖**。
- 客观检验顿帧程度（代理指标）：
  ```bash
  ffmpeg -hide_banner -i x.mp4 -vf "scale=64:36,signalstats,metadata=print:key=lavfi.signalstats.YAVG" \
         -f null - 2>&1 | grep -o "YAVG=[0-9.]*" | sed 's/YAVG=//'
  ```
  然后算相邻帧差：**静止帧占比高 + 偶发大跳变 = 顿帧**；差值平稳 = 平滑插值。

### 「定格（stop motion）」画风配方（已实测有效）

参考 Apple《Share Your Gifts》（**真·实体微缩布景 + 逐帧拍摄 + CG 增强**，作者工具含 **Dragonframe**）。
prompt 骨架 —— 六条缺一不可：

1. `handcrafted miniature diorama set built for a stop-motion film`
2. **手作材质**：`foam board, card, balsa wood, wool, felt` + `brush strokes, card edges, glue seams, slightly imperfect construction`
3. **暖色实用光**：`practical miniature lamps hidden inside, string lights glowing amber`
4. **深蓝夜色**：`deep indigo night sky`（不是灰）
5. ⭐ **霓虹点缀**：`soft magenta and cyan neon signs` —— **最容易漏，也是「像不像」的分水岭**
6. **镜头语汇**：`shallow depth of field with a tilt-shift miniature feeling, macro lens, subtle film grain`

> ⭐ 第 5 条说明了一件关键事：**参考图锁的是「色板」= 画风的指纹。**
> 结构（微缩村 / 暖窗 / 雪）文字说得清；**色板只能看图给**。
> 实测：纯文字 → 霓虹消失，滑向通用「琥珀+深蓝」圣诞村；加 1 张参考图 → 品红/青全回来。

### 第 4.6 步 · 快节奏蒙太奇（`assemble_montage.py`）

**节奏在剪辑里，不在模型里。** 出片最短 4s，但快切要 0.3–0.8s 一刀 ——
**绝不能靠出片凑刀数**。让一个素材被切三次，每次都是「不同的镜头」：

| 手法 | 做法 | 成本 |
|---|---|---|
| **静帧推镜（punch-in）** | 同一张关键帧 `zoompan` 推两次 → 两个景别 | 0 |
| **二次构图** | 片段**先升到 1280×720** 再 `crop` 到 0.6（不升采样会发虚） | 0 |
| **不同时间区间** | 同一条 4s 片段取 0.2–1.2 与 1.6–2.3 两段 | 0 |
| **硬切** | 快切片**不用交叉溶解**（溶解泄节奏） | 0 |

实测账：**7 静帧 + 3 片段（4s/360p）→ 14 刀 / 9.15s（平均 0.65s 一刀）**。

```bash
$P assemble_montage.py specs/<x>-montage.json           # 慢片用 assemble_reel.py，快片用这个
$P assemble_montage.py specs/<x>-montage.json --dry-run # 列分镜表，零消耗
```

- `"kind":"image"` → `{"src","len","zoom":"in|out","zoom_to":1.38,"focus":[0.5,0.36]}`
- `"kind":"clip"`  → `{"src","start","len","vf":"scale=1280:720,crop=iw*0.62:ih*0.62:..."}`
- 总时长 = `sum(len)`；**默认全硬切**。
- `"audio":{"pulse":{"freq":118,"volume":0.42,"gate":0.06}}` → **每一刀开头一个低频脉冲**
  （ffmpeg 现场合成，零成本）。节奏立刻「立起来」—— **要节奏感不需要音乐。**
- ⚠️ `aevalsrc` 必须显式 `:c=stereo`，否则跟片段音轨 `concat` 会失败（已处理）。

### 第 4.7 步 · 先看图的第 4 课：**prompt 的用词会决定相机语言**

C1 暴露的三个问题（都是我的 spec/prompt 错，不是 G-Labs 的问题）：

| 症状 | 根因 | 改法 |
|---|---|---|
| 有角色却不像 | **漏挂角色参考图**（尤其背影镜） | **凡出现角色的镜头一律挂角色 ref**，一条都不能省 |
| 布景突然「变成一个盒子」 | prompt 写 `open-fronted ... cubicle` → 字面诱导「从外面看盒子」 | 删掉，改写成 `camera is inside the miniature room, we never see the outside walls of the set` |
| 头发变螺旋壳 | `thick coiled rounded curls` 被理解成螺旋 | → `thick soft rounded ribbon curls` |
| 冒出脖子 | 只写「无脖子」不够 | 加全大写 `NO neck` + `the head sitting directly on the shirt collar` |

> **一句话：同一句场景 prompt 会在不同镜次生出不同的相机语言。**
> 把「机位在哪、看不看得见布景外框」明确写死，否则镜与镜之间会「跳世界」。

### 第 4.8 步 · 想要一条片子可复现？**把账号钉死**

G-Labs 默认**按请求轮流挑号**（app 日志：`accounts=2`）。同一片子里镜 1 走 A 号、镜 2 走 B 号。
→ 钉死后日志变 `accounts=1`：

```bash
GLABS_ACCOUNT_ID=<uuid> $P gen_frames.py specs/<x>.json    # gen_clips.py 同样认
```
uuid 从 app 的 `flow_accounts.json` 的 `_runtime_uuid` 取（`glabs.py accounts` 不一定显示）。

### 第 4.9 步 · 音乐：`assemble_reel.py` 已支持外部音乐轨

```json
"music": {"path":"<abs mp3>","start":0.0,"gain":0.9,"fade_in":0.8,"fade_out":2.0,"amb_duck":0.35}
```
自动裁到片长 → 淡入淡出 → **把环境声压到 35% 给音乐让位**（简易 ducking）。
**文件不存在时会跳过并警告**（画面照常出）→ 所以可以先出画面、再补音乐，重跑一次 spec 即可。

**音乐从哪来（2026-09-20 查实）**：
- ⭐ **`opencli suno generate`** —— 最省事。`--instrumental` 出纯伴奏，
  `--tags "…, 84 BPM, soft piano"` **能指定 BPM**（就能卡着拍子剪）。
  前置：Chrome 里登录 Suno **并人工过一次验证码**（`Captcha: Required (solve in UI)`）。
  免费档 **无商用授权**；要发布得升付费档。
- Google Flow Music（`flowmusic.app`，Lyria 3 Pro）**没有公开 API**。要走它只能用
  `opencli browser <session> bind` 挂上已登录标签页去驱动（无适配器，较脆）。
- G-Labs app **没有任何音频/音乐路由**（已核对二进制里的 `/api/*`）。

### 第 5 步 · 质检（别跳过）

```bash
# 抽帧看有没有黑边/融化
ffmpeg -ss <t> -i out.mp4 -frames:v 1 chk.jpg
```
- 用 contact sheet 一次看 6–10 帧，覆盖每个转场点。
- 有 `<video>` 的页面用 `agent-browser` 实测：
  ```bash
  agent-browser open "file://$PWD/page.html"
  agent-browser eval 'JSON.stringify([...document.querySelectorAll("video")].map(v=>({f:v.currentSrc.split("/").pop(),rs:v.readyState,dur:v.duration,w:v.videoWidth})))'
  agent-browser close
  ```
  `readyState=4` = 完整加载；`duration` 对得上 = 文件没坏。
  ⚠️ 页面里 `loading="lazy"` 的图，先 `eval` 把它们设成 `eager` 再看。

### 第 6 步 · 出看板页

- 加进 `003-Workbench/_build/build_phase2.py`（`NAV_ITEMS` + 新 `build_*` 函数 + `main()` 注册 + `patch_index_cards`）。
- **别忘同步**：`NAV_ITEMS`、`patch_index_cards` 的正则与卡片数、`main()` 注册表。少一处就出现孤立页。
- 产物页要能**双击直接开**：相对路径 + 数据内联，不依赖服务器。

## ⚠️ 工程坑（本环境实测）

| 坑 | 症状 | 解法 |
|---|---|---|
| **⚠️ 出片安全过滤** | `error_code=0 DANGEROUS`，**不说是哪句** | 避开 `dying` / `final movement` / `go completely still` / `slumped face-down` 这类词 → 换 `rests quietly` / `calm and peaceful` / `end of a long day` |
| **Edit 工具偶发不持久** | 报告成功，但文件没改 | 改完**立刻读回验证**；关键改动用 Python `replace` + 一次写入 |
| **bash `grep` 不可靠** | 明明有却返回空 | 用 Grep **工具**，别用 shell grep |
| **zsh 不分词** | 循环里 `set -- $spec` 拿到整串 | 用数组或改 Python |
| **ffmpeg 无 drawtext** | `No such filter: 'drawtext'` | 去掉文字标注，或换 `subtitles` |
| **TCC 保护目录** | G-Labs 报 `UPLOAD_ERROR` | 只有 `--backend gateway` 需要先复制到 `~/.hermes/drama-gateway/media/`；native 走 base64 不受影响 |
| **md 星号漏到 HTML** | 页面上出现字面 `**粗体**` | 生成后 `re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", ...)`，并校验 `count("**")==0` |

## 交付清单（缺一不可）

- [ ] `Assets/glabs/<项目>/` —— 关键帧 + 动态 + 成片 + poster
- [ ] `003-Workbench/behance/<项目>-run.html` —— 可播看板（导航 + index 卡片都挂上）
- [ ] `Wiki/Research/<项目>实测-YYYY-MM.md` —— 笔记
- [ ] 若暴露了影响选型的问题 → `HermesBrain/Memory/Decisions/`
- [ ] `000-下一件事.md` + `Daily/` + `.workbuddy/memory/` 同步
- [ ] 校验：0 断链、0 markdown 星号残留、视频 `readyState=4`

## 已验证过的「能不能」结论（别再测一遍）

> ⭐ **总纲：风格迁移（「像那一类」）AI 很行；角色还原（「就是那一个」）不行。**
> 差别在任务性质 —— 前者只要求统计味道对，后者要求身份特征逐条对上。

- **抽象/无具体物体**（场景、氛围、几何）→ AI 甜区，成功率极高。
- **⭐ 某种画风**（stop motion / Claymation / 纸艺 …）→ **✅ 能拿**。
  参考图锁色板；材质与景深在运动里能守住；**换场景也不会漂**（实测 2026-09-19）。
  → 这是**正面结论**，适合作为管线里的「画风层」。
- **⭐ 自有 IP 角色 + AI 场景**（3D 本体当参考图）→ **✅ 走通了**（C1 实测，2026-09-19）。
  **5/5 个镜头逐特征零丢失。** 关键在下面三件事。

### ⭐⭐ 核心配方：两张参考图，各管一件事（C1 实测）

> **角色 ref 保身份，风格 ref 保色板 —— 两者是「叠加」，不是竞争。**

A/B 实测（同场景同 prompt，唯一变量是给几张 ref）：

| | 只给角色 ref | 角色 ref + 风格 ref |
|---|---|---|
| 角色特征 | ✅ 全对 | ✅ 全对 |
| 场景结构 | ✅ 对 | ✅ 对 |
| **色板** | ❌ 丢了，退化成中性色 | ✅ **整套风格色板回来了** |

**别担心「多喂一张风格图会稀释角色」——实测不会。**
该担心的是反向：**不给风格图，你就拿不到那个色板。**

### ⭐ 角色还原度的三个可干预变量

> **还原度 ≈ 参考图质量 × 角色设计的辨识度 ÷ 改动幅度**

| 变量 | 怎么做 |
|---|---|
| 参考图质量 | 用**干净的 3D 定稿渲染**。**不要从剧情画面里裁**（B 轮就栽在这：小、有背景、有透视） |
| 角色辨识度 | 高对比、不会被误认成通用角色的特征（例：巨大厚唇 / 盘卷发 / T 形眼） |
| 改动幅度 | **只换场景和光**；换姿势体系 / 换服装会明显掉 |

- **⚠️ 大动作幅度会漂**：prompt 写「脸朝下趴桌上」→ 模型给「瘫回椅背、头前垂」。
  这是**姿势漂移，不是身份漂移**（特征一个没丢）。要精确控制姿势，就得走 3D。
- **有具体角色但不给干净 ref** → 跨镜一致性锁不住（背刺颜色会变、不显眼特征会丢）。
- **密集重复结构**（牙齿、栅格、文字）→ 明确失败模式。
- **风格会被「美化」**成更干净高级的通用卡通 → **品牌识别度反而下降，且不易察觉**。
  （在「画风迁移」任务里这条反而变成可接受，因为你要的就是那种味道；
  在「角色还原」任务里它是致命伤 —— 因为你丢的是品牌身份。）

### 分层合成（还没做，但这是定论的完整形态）

C1 里角色**仍然是 AI 重绘的**。100% 保真的做法是：
**AI 只出空场景板 → 角色单独 3D 渲染（带透明通道）→ 后期（AE / PR）分层合成。**
角色那层完全可控，AI 只做它擅长的。**下一次该试这个。**

## 五个已完成案例（可作模板）

| 轮 | 参考 | 测什么 | 结论 | 看板 |
|---|---|---|---|---|
| B | Mectron（牙科吉祥物） | 角色还原 | ❌ 跨镜漂移 | `behance/mectron-run.html` |
| C | Apple《Share Your Gifts》 | 画风迁移（定格） | ✅ 拿得到 | `behance/syg-run.html` |
| C1 | 自有 IP 小厚先生 × 定格 | 3D 本体 + AI 场景 | 🟡 5 镜守住，但背影镜翻车 | `behance/xiaohou-run.html` |
| C2 | ｢동네가 내 운동장｣（Walps） | **快节奏蒙太奇** + 修 C1 的问题 | 🟡 14 刀 / 9.15s，但**被判定「不好看」** | `behance/fastcut-run.html` |
| C3 | 熊猫莫莫（自有 IP） | **Character Sheet 验证** + 修正画质 | ✅ **背影镜首次成立**，17.6s / 720p | `behance/momo-run.html` |

### ⭐ Character Sheet 是「非正面视角」的唯一解（C3 已验证）

对照实验（唯一变量 = 背影镜有没有给背面参考）：

| 角色 | 背面参考 | 背影镜结果 |
|---|---|---|
| 小厚先生 C1 镜 4 | ❌ 只挂风格图 | 🔴 崩 —— 螺旋蜗牛壳头发 / 长出脖子 / 耳朵消失 |
| **莫莫 C3 镜 4** | ✅ `momo-back.png` | ✅ **成立** —— 圆头 / 双耳 / 兜帽搭肩 / 尾巴绒球 / 短腿圆掌 全对 |

做法：有 3D 本体 → **转一圈渲 4 视角（正/侧/背/3-4）+ 表情 4–6 个 + 材质近景与主色 HEX**，成本≈0。
⚠️ **不要整张 sheet 当一张参考图喂** —— 8 宫格缩到一张图，每个角度只剩很小像素。
**sheet 存进 vault 当 IP 资产，喂的时候按镜头需要单独裁一张出来。**

### ⭐⭐ 「好看」的四个变量（C2 翻车 → C3 修好的教训）

> **分辨率 · 运动量 · 光比 · 构图密度** —— 这四个决定观感，跟模型无关。

| 变量 | 做错会怎样 | 做对 |
|---|---|---|
| **分辨率** | 360p → 糊 | 至少 **720p**。要给人看的片子别在分辨率上省 |
| **运动量** | 靠**静帧推镜**（punch-in）凑刀数 → 像幻灯片 | 主力镜头**用真生成的动态**；punch-in 只当补充 |
| **光比** | 日光 + 米色/奶油色板 → 灰、平、没劲 | **硬主光 + 冷阴影 + 一个彩色点缀**（夜景 + 暖台灯 + 品红/青霓虹） |
| **构图密度** | 道具堆满、无焦点 | **每镜一个焦点 + 留白**；少而精的道具 |

**加一条**：写死 `camera is inside the miniature set, we never see the outside walls of the set` ——
否则会露出布景外框，「手工感」立刻变成「手工课的廉价感」。

> ⚠️ **取舍教训：不要把「省额度」排在「好看」前面。** C2 为了省，四条全调错了。
