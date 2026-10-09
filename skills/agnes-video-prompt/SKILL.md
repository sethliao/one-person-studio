---
name: agnes-video-prompt
description: 给 Agnes Video 2.5 / 2.5 Flash 写视频提示词并出片 —— 走**官方 API**（推荐，快、可传参考图）或 Pavo AI 网页（app.pavo-ai.cn）。当用户说「用 Agnes 出个片」「Pavo 上写个提示词」「2.5 Flash 试一版」「免费跑一条视频」「按这个参考图生成视频」时使用。含官方三段式公式、素材槽位表、时长/比例核对、opencli 操作配方。
agent_created: true
---

## ⛔ 通道选择：优先 API，别默认走网页

| |官方 API | Pavo 网页 |
|---|---|---|
| key | keychain `agnes-ai` | 网页登录态 |
| 参考图 | ✅ **Data URI 直接传**（2026-10-05 实测） | ⛔ 只能网页上传（opencli upload 走不通，见 §三） |
| 拿到结果 | 轮询 JSON，约 2–4 分钟 | 3–6 分钟 + 重载页面 |
| 适合 | **脚本化、可复现、要传参考图** | 手工试 prompt、试分镜 |

⛔ **Pavo 和 Agnes 是同一家公司**（Agnes AI / Pavo AI）。
模型、提示词公式、限免政策**完全一致** —— 网页上试出来的 prompt，API 上直接能用。
他给你 API key 的意图就是**让你走 API**，别再默认开浏览器。

## API 快速通道（2026-10-05 实测跑通）

```bash
K=$(security find-generic-password -a seth - s agnes-ai -w)   # 从 keychain 读，不写明文
B=https://api.agnes-ai.cn/v1        # 国内站
# B=https://apihub.agnes-ai.com/v1 #国际站
```

**创建**（`POST /videos`）→ 拿 `video_id` → **轮询** → 下载顶层 `url`：

```bash
curl -sS -X POST "$B/videos" -H "Authorization: Bearer $K" -H "Content-Type: application/json" -d '{
  "model":"agnes-video-2.5-flash","prompt":"...","seconds":"8",
  "mode":"text","size":"720P","aspect_ratio":"16:9"}'
# → {"video_id":"task_xxx","status":"queued"}

# 🚨 轮询必须带 model_name，否则 keyframe/reference 模式查不到
curl -sS "https://api.agnes-ai.cn/agnesapi?video_id=$VID&model_name=agnes-video-2.5-flash" \
  -H "Authorization: Bearer $K"
# status: queued → pending → in_progress → completed（顶层 url 是文件地址）
```

### ⭐ 参考图用 Data URI（不需要图床，2026-10-05 实测通）

官方文档写「媒体 URL 应可公开访问」，但 **Data URI 照样被接受**（实测 Agnes Video 2.5 Flash `mode=reference` 正常出片）：

```bash
B64=$(base64 -i参考图.jpg | tr -d '\n')
# images: ["data:image/jpeg;base64," + B64]
```

prompt 里用 **`<Picture 1>` 指代**（不是 `@图片1`，那是网页端的写法）：

```
以 <Picture 1> 中的角色为人物参考，锁定外观：厚脸盘、米色连帽卫衣、圆眼细眉。
8秒，16:9 横版。[角色]在清晨工位从屏幕前抬头，缓慢伸懒腰。
黏土定格质感，柔和晨光，浅景深。
不要生成可读文字。不要额外添加背景音乐。
上传图片仅作为一致性参考，最终视频不能直接显示或拼贴该图。
```

**实测结论（2026-10-05）**：加了参考图后**角色明显对了**（厚脸盘/卷发/浓眉都锁住），
但**衣服没锁住**（参考图纯米色→ 出片粉白横条纹），且prompt 里写了的动作幅度要够大才动得起来。

### ⭐ 一条命令跑完（推荐，别手搓 curl）

```bash
P=~/.workbuddy/binaries/python/envs/default/bin/python
S=$VAULT_PATH/004-Tools/agnes.py

$P $S --ref 参考图.jpg --prompt "…" --seconds 8 --aspect 16:9 --out 出片.mp4
```

它已经把踩过的坑全封进去了：Data URI 转换 ·轮询带 model_name · key 从 keychain 读 ·
**提交前校验 6 项**（秒数 4–12 / 参考图 ≤5 / 音频 ≤3 / 模式与素材匹配）·
**撞 429 自动退避重试** · 出片完自动调`ep-qa.py` 体检。

### 🚨 免费用户有速率限制（2026-10-05 实测，官方文档没写）
- 一分钟内提交多条会撞 `429 rate_limit_exceeded`，**等约 60 秒恢复**
- ⛔ 429 发生在**创建之前**，**不扣额度**
- 批量跑时**每条之间留 ≥60 秒**。脚本已内置退避，但批量时还是要留间隔
- ⚠️ 免费用户限流解法是升级 Token Plan —— 但**限免期本来就不花钱**，别急着升

### 模型对照（2026-10-05 官方 catalog 实读）

| 模型 | size | 参考图 | 参考音频 | 参考视频 | 价|
|---|---|---|---|---|---|
| `agnes-video-2.5-flash` | 仅 720P | ≤5 | ≤3 | ⛔ | **限免¥0** |
| `agnes-video-2.5` | 720P/1080P/1K/2K | ≤8 | ≤3 | ✅ | $0.025/秒起 |

⛔ **非 Flash 是付费的**（8 秒 720P 约 $0.2≈ ¥1.4）—— 跑之前先报预估等他点头。
⚠️ 限免政策会变，**跑之前先看当前价**。

### 声音的真相（别再误判）

- Flash **会出环境声**，但很轻：实测 **−37dB**（有环境声）vs 纯静音 **−59dB**。
- ⚠️ **别用「音量低于 −40dB = 静音」判** —— 我这么判过，被他一句「我昨天看是有声音的」纠正。
  真实安静环境声就在 −40dB 上下。
- 用 `ep-qa` 体检时阈值已是 **−50dB**（实测标定，不是拍的）。
---

# agnes-video-prompt · Pavo AI 上的视频提示词

## 什么时候用

- Seth 要在 **Pavo AI（`app.pavo-ai.cn`）** 上出视频，或要我写/改一条 Agnes 提示词。
- 要在**不烧额度**的前提下试 prompt、试分镜、试口型。
- 要给某个 IP（小厚先生 / 熊猫莫莫 / Paikea）出**试镜版**。

**成片不走这条** —— 对外交付回 `gflow`（Google Flow）。Agnes Flash 是**试镜通道**，不是交付通道。

> 详细背景与平台事实：vault 内 `Wiki/Pipeline/Agnes-Pavo/README.md`
> 官方原文：`Wiki/Pipeline/Agnes-Pavo/官方提示词指南-原文.md`（⛔ 镜像页，不手改）

---

## 一、公式（先套骨架，再填内容）

```
完整提示词 = 【参考素材说明】 + 【核心创意】 + 【画面过程说明】
```

```text
【参考素材说明】@图片1 作为 XX 参考，锁定……（具体特征）；@图片2 作为 XX 参考，锁定……（无素材时整段跳过）
【核心创意】XX秒，16:9 横版。[主体]（@图片1）在[地点]（@图片2）[事件]。[风格]，[运镜]。
【画面过程描述】
0–X秒：正向：[景别]，[主体][动作]，[环境/光线]，[音效]。
        反向：不要[……]；不要[……]。
X–X秒：正向：[切到XX景别]，[主体][动作]，说："[台词原文]"。
        反向：不要[……]。
▍镜头约束：……
▍声音：……。不要人声、对白、歌词和旁白。
```

**检查项**（缺一条就容易崩）：

| # | 检查 |
|---|---|
| 1 | **开头就写「X秒，A:B 比例」**，X 必须**等于**界面设置里的时长 |
| 2 | 每个素材都写了 **`@图片N 作为 XX 参考，锁定…`** |
| 3 | 每个时间段都有 **反向**（不想要的：BGM / 切镜 / 多余手指 / 可读文字 / 参考图被直接拼贴） |
| 4 | **一镜到底 与 多分镜 二选一** —— 选了一镜到底就不要出现「镜头 N」 |
| 5 | 台词**写原文**，且**长度对得上 shot 时长**（3 秒别塞一段） |
| 6 | 跨 shot 的台词写明「（接上个 shot 继续说）」 |
| 7 | 画面里要出现的**文字/标题/logo 写原文**；不要文字就写「不要生成可读文字」 |
| 8 | 角色一致性：**必须挂人物参考图** + 补一句「仅作为一致性参考，不要直接复用/拼贴该图」 |

### 素材槽位（每个上传素材都得认领一个）

`人物参考`（锁脸）· `物体参考` · `场景参考` · `关键帧`（写明首帧/尾帧）· `音色参考` · `故事版` ·
`风格参考` · `构图参考` · `音频复用` / `音频部分复用` · `动作参考` · `运镜参考` · `视频编辑`

### 反向指令的常用写法

```
不要额外添加背景音乐。 / "non_diegetic_music": N/A
不要切镜。 / 不要出现第三只手、多余手指、手指粘连。
不要生成可读文字 / 不要出现任何文字、Logo、品牌标识。
不要生成慢动作、快动作、掉帧或运动拖影。
上传图片仅作为一致性参考，最终视频不能直接显示、复用或拼贴参考图 —— 必须生成全新的动态画面。
```

---

## 二、⚠️ 写之前必核的三件事（踩过的坑）

1. **时长要对齐** —— 界面右下角 `Auto / 4s / 720p` 那个数字，必须和 prompt 里的秒数一致。
   （2026-10-03 他那个会话 prompt 写 12 秒 / 七段节奏，设置却是 **4s**。）
2. **比例要对齐** —— 参数面板里比例（`9:16 3:4 1:1 4:3 16:9 21:9`）要跟 prompt 的写法一致。
   要横屏就必须写「必须严格保持 16:9 Landscape」，并在设置里选 16:9。
3. **只有 `Agnes Video 2.5 Flash` 是免费的** —— 用前在模型下拉里**看一眼当前标签**，
   免费/折扣是会变的。其他模型一跑就扣积分。
4. **先读该角色的视频约束**（写进 `Wiki/<IP>/角色一致性描述.md`）：
   - **头大 / chibi 角色别写「特写/怼脸」**（如小厚先生头身比 1:1，最后镜头推进到脸会比例失衡）→ 用「中景/中近景」。
   - **起始帧 = prompt 第一段动作**：Agnes 执行得很字面。想让角色从「正视镜头」开始，第一段就不能写「低着头」。

**别交给视频模型的东西**（库内铁律，来自 [[AI出片实测教训]]）：
**信息图 / 图表 / 文字卡** → 走 HyperFrames。视频模型会写错字且不可改。

---

## 二·五、A/B 实测结论（2026-10-03，小厚先生）

- **B 长 prompt（官方三段式）明显更好**：角色还原、动作可控、画面完整都优于 A 短 prompt。
- ** Agnes 的「具名槽位」有效**：`@图片1 作为人物参考` 挂对后，长 prompt 不会稀释参考图。
- **详细记录**：`Wiki/Pipeline/Agnes-Pavo/README.md` §五·五 · `Assets/小厚先生/agnes-ab-2026-10-03/`

---

## 三、驱动网页（opencli · 2026-10-03 实测）

```bash
S=pavo
opencli browser $S open "https://app.pavo-ai.cn/chat?conversationId=<id>" --window background
opencli browser $S state          # 读结构 + 可点元素索引
```

实测选择器：

| 目标 | 选择器 |
|---|---|
| 输入区 | `[contenteditable=true][aria-label="Intelligent input area"]` |
| 发送 | `button#dle_send_button`（生成中 aria-label 变 `Stop`） |
| 上传素材 | `input[type=file]`（`.hidden`，accept: `image/jpeg,png,webp` + `audio/mpeg,wav`，多选） |
| @ 资产选择器 | `button#dle_material_picker`（⚠️ 资产库空时会说「暂无素材，请先上传」） |
| 参数面板 | `button#dle_setting` → 比例 / 时长（4–12s 逐秒）/ 分辨率（720P） |
| 三个下拉 | `document.querySelectorAll('.ant-select')[0..2]`＝ `图片生成\|视频生成` · `模型` · `全能模式\|首尾帧` |
| 附件卡片 | 缩略图 `img[src*=chat_attachment]`；删除钮 = `img.closest('div.group').querySelector('button')`（去重时用） |

> ⚠️ 下拉是 **Ant Design Select**，普通 `.click()` **打不开** —— 要依次派发
> `mousedown` + `mouseup` + `click`（`new MouseEvent(t,{bubbles:true,cancelable:true,view:window})`）。
> 读选项：`.ant-select-dropdown .ant-select-item-option`。

### ⛔ 上传图：`opencli browser upload` 走不通（2026-10-03 实测）

`opencli browser <s> upload 'input[type=file]' <path>` 一律报
`Page.fileChooserOpened not received within 5s`（把 input 临时改成可见也无效 —— 文件选择器事件没被桥接过来）。

**✅ 绕法：本地 CORS 服务 + 页面内 fetch 造 File**（实测成功）：

```python
# /tmp/serve_cors.py —— 只服务那张参考图所在目录
import http.server, socketserver
ROOT = "<参考图所在目录>"
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*a,**k): super().__init__(*a, directory=ROOT, **k)
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Private-Network","true")
        super().end_headers()
socketserver.TCPServer.allow_reuse_address = True
socketserver.ThreadingTCPServer(("127.0.0.1",8899),H).serve_forever()
```

```bash
nohup /usr/bin/python3 /tmp/serve_cors.py >/tmp/serve_cors.log 2>&1 &
```

```javascript
// 然后在页面里（opencli browser <s> eval）
const r = await fetch('http://127.0.0.1:8899/xh-front-cut.png', {cache:'no-store'});
const f = new File([await r.blob()], 'xh-front-cut.png', {type:'image/png'});
const dt = new DataTransfer(); dt.items.add(f);
const i = document.querySelector('input[type=file]');
i.files = dt.files;
i.dispatchEvent(new Event('input',  {bubbles:true}));
i.dispatchEvent(new Event('change', {bubbles:true}));
```

> ⚠️ 每次调用都会**追加**一张 —— 想只留一张，用附件卡片的 `button` 删掉多余的（见上表）。
> ⚠️ https 页面 fetch `http://127.0.0.1` 实测**可用**（Chrome 把 localhost 当可信源），但要
> `Access-Control-Allow-Private-Network: true` 才稳。

### 取结果（两个坑）

1. **设置/模型下拉没关 → 发送会被拦截** —— 2026-10-03 Momo 那次就是模型下拉还开着，点发送没反应。
   **解法：发送前一定要先 `opencli browser <s> keys Escape`** 关掉所有浮层，再点 `#dle_send_button`。
2. **UI 不会自动刷新** —— 生成早就完了，页面还停在「正在准备…」。
   **解法：重载会话页** `opencli browser <s> open "<会话URL>" --window background`，结果立刻出现。
2. **成片 URL 只在 `<video>` 里**：`#chat-page-container video` 的 `src`。
   同页还会有**首帧图** `img[src*=self-v03-first-frames]`，命名带同一个 hash，可一起下。

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
curl -s --noproxy '*' -A "$UA" -o out.mp4 "<video src>"
curl -s --noproxy '*' -A "$UA" -o first.jpg "<first-frame src>"
```

> ⚠️ **CDN 能直连**（`cos-aigc-default.agnes-ai.cn`），但要带 `--noproxy '*'` + 正常浏览器 UA。
> ✅ 2026-10-03 实测：1280×720 / 24fps / 5.17s / ≈1.1–1.2 MB。

### 跑一轮的完整时间成本

提交 → 成片 ≈ **3–6 分钟**（5s / 720p）。轮询别写「检查 `.mp4` 出现在输出里」这种判断 ——
我踩过：循环里只输出了计数 `v.length`（数字），却拿 `.mp4` 去匹配字符串，**永远不触发**，
白等 5 分钟。**直接匹配数字变化，或干脆隔 2–3 分钟重载一次页面。**

**纪律**：
- ✅ **Seth 已授权我直接驱动网页跑 `Agnes Video 2.5 Flash`**（免费、不扣积分），所以我可以直接跑单条/少量测试。
- 收费模型 / 批量跑 / 用「短剧/画布/AI剧本」等**非视频生成功能前，先报预估并等他点头**。
- 免费模型**不烧钱**，但单次提交后也要等 3–6 分钟，别在他着急时堆队列。

---

## 四、收尾

生成完**不要自己读图做审美判断**（库内铁律：**验收归 Seth**）。
→ 正确动作：把结果拼成**对照表**（用 `003-Workbench/_build/make_ab_sheet.py`）推给他，等他一句结论。
→ 他说「某镜崩了」→ **第一动作是读 prompt 查素材槽位**（零消耗），不是重跑。

---

## 五、可复用：一键跑一条视频

技能目录下附带 `scripts/run_agnes_recipe.py` —— 把 prompt 文件、参考图、时长/比例传进去，自动走完
「开新会话 → 设参数 → 传图 → 填 prompt → 发送 → 等 4 分钟 → 下载成片」。

```bash
cd ~/.workbuddy/skills/agnes-video-prompt/scripts
python3 run_agnes_recipe.py \
  --prompt /path/to/prompt.txt \
  --ref /path/to/ref.png \
  --ratio 16:9 \
  --duration 5 \
  --outdir $VAULT_PATH/Assets/<IP>/agnes-YYYYMMDD
```

> 这脚本目前只支持**单张参考图** + **Agnes Video 2.5 Flash**。复杂情况（多图/首尾帧/音频）仍走 §三的手动步骤。
