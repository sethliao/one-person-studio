---
name: drama-claw-hermes
description: Run the local DramaClaw×G-Labs video pipeline.
tags:
  - dramaclaw
  - video-pipeline
  - glabs
  - mcp
agent_created: true
---

# DramaClaw × (G-Labs + cursor) — 本地短片流水线

## 何时使用
- 用 DramaClaw CE 生成短剧/短片（剧本→分镜→图片→视频→配音→合成）
- 需要把 DramaClaw 接到本地 G-Labs (图片/视频) + Antigravity CLI (LLM) + Voice Studio (TTS)
- 需要让 WorkBuddy 用 MCP 驱动 DramaClaw 全流程

> **只要出图/出片、不跑全流程？用 skill `glabs-studio` 直连 G-Labs 原生 API 更快**（6 个端点，含免费的本地放大）。
> 本 skill 负责 DramaClaw 全流程与 gateway 适配层。

## ⚠️ 2026-09-19 三处断裂已修（照这条排查）
1. **app 改名**：`G-Labs Automation` → **`G-Labs Studio`**（`/Applications/G-Labs Studio.app`）。端口仍是 **8765**。
2. **key 随之重置**：`gRjd5P…` → `i-fi2a…`，旧 key 一律 **401 Invalid or missing API key**（静默全链路失败）。
   唯一真源 = `~/Library/Application Support/G-Labs Studio/webhook_config.json` → `api_key`。
   一键修复 + 重启 gateway：
   ```bash
   P=~/.workbuddy/binaries/python/versions/3.13.12/bin/python3
   $P ~/.workbuddy/skills/glabs-studio/scripts/glabs.py key --sync
   /usr/bin/python3 ~/Code/drama-claw-hermes/bin/daemon-run.py \
     --log ~/Code/drama-claw-hermes/logs/gateway.log --env NO_PROXY='*' \
     -- /usr/bin/python3 ~/Code/drama-claw-hermes/agy-shim/drama_gateway.py --port 8790
   ```
   ⚠️ gateway **启动时只读一次 key**，改完必须重启才生效。
3. **代理劫持回环**：终端环境带 `HTTP_PROXY=127.0.0.1:5xxxx`，curl/urllib 会把它用在 127.0.0.1 上 →
   **所有本机 API 调用变 502 `upstream connect failed: Connection refused (os error 61)`**。
   curl 一律加 `--noproxy '*'`；Python 子进程传 `env={"NO_PROXY": "*", **os.environ}`。
   看到 `os error 61` 且格式不像 Python —— 是代理，不是服务挂了。

`gateway` 的 `[glabs]` 配置在 `~/.hermes/drama-gateway/providers.ini`（`key_env` 优先 → `key_file`），
`~/.hermes/.env` 里的 `GLABS_API_KEY` 优先级最高。

## 快速定位（防重搜，2026-09-03）
- Repo: `~/Code/drama-claw`（origin=sethliao/dramaclaw；本地 feat/* 分支直接推 origin，patch 合入 seth-patches）
- Vault 项目 hub: `080-Agent/熊猫莫莫/`（DramaClaw-工作流 / 分集日志 / 故事源 / 素材索引 / 莫莫角色）；Paikea: `080-Agent/Paikea/`
- Plan 笔记约定: `080-Agent/plans/YYYY-MM-DD_HHMMSS-<slug>.md`，body 分 `Task N`（2-5min 粒度，每任务一提交）
- Kanban: `hermes kanban ls`（default board）；任务验收/状态回填先问 Seth 再动手
- 新功能落地 = 代码 push + 更新 skill + 更新 vault 工作流笔记，三端一致

## Append Episode「加集」（2026-09-03，feat/episode-append 已 push origin，PR 待开）
- 端点: `POST /api/v1/projects/{project}/episodes/append`，body `{"text":"## Episode 5：春节\n场景：...\nMomo: ..."}`
- 语义: novel.txt 追加 → ChapterDetector 解析新集（`Episode N`/`第X集`/`第X章`）→ `add_episodes()` 合并（旧集不动）→ 新角色按名去重
- 编号: 自动 max+1；text 自带集号冲突 → 409；未导入小说 → 400。实现 commit `8f9411bc`

## 架构（Hybrid Overlay，上游零改动）
```
DramaClaw CE (upstream @ ~/Code/drama-claw, pristine, git pull 干净)
  └─ settings.db: model_gateway_mode=custom → http://127.0.0.1:8790/v1
        └─ drama-gateway (@ ~/Code/drama-claw-hermes/agy-shim/drama_gateway.py)
             ├─ /v1/chat/completions  → agy -p (fallback DeepSeek)
             ├─ /v1/embeddings        → SiliconFlow BGE (key from ~/.hermes/.env)
             ├─ /v1/images/generations|edits → G-Labs :8765 /api/image/generate
             ├─ /v1/videos/generations (Grok 式 submit→poll) → G-Labs :8765 /api/video/generate
  │     ⚠️ 有参考图/参考视频 → Omni Flash components 模式（参考图即 ingredient）；
  │        无参考 → text_to_video 纯文生视频（2026-09-10 Seth 批准放开，实测 omni-flash 10s 通过）。
  │        仍不用 first_frame / start_end_image（Seth 要求：无黑边/僵硬锁定帧）
             └─ /v1/audio/speech      → Edge TTS（默认免费男声 zh-CN-YunjianNeural）| Volc doubao（备选）| Voice Studio（已弃用）
```

## 直接驱动 gateway（curl 配方，2026-09-19 实测）

**不想跑整套 DramaClaw、只想出图/出片时，直接打 gateway :8790 的 OpenAI 兼容端点最快。**
（:8790 没有 `/v1/models`、没有 `/openapi.json` —— 别去探，路由写在 `agy-shim/drama_gateway.py` 的 `_dispatch()`。）

> ⚠️ **所有 curl 都要加 `--noproxy '*'`**，否则被环境里的 `HTTP_PROXY` 劫持 → 502 `os error 61`。
> 下文配方为简洁省略了它，实际执行请补上。（或改用 skill `glabs-studio` 的 `glabs.py`，它内部已处理。）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/v1/images/generations` | POST | **阻塞式**：内部 submit G-Labs 202 → 自动 poll → 返回 `data[].local_path`。实测 **~40s/张** |
| `/v1/videos/generations` | POST | **异步**：立即返回 `request_id`（形如 `glabs-xxxx`） |
| `/v1/videos/<request_id>` | GET | 轮询，`status` ∈ `running`/`done`；完成时带 `result_url` + `local_path` |
| `/v1/audio/speech` | POST | TTS（**不是音乐生成**，别指望它配乐） |
| `/v1/chat/completions` · `/v1/embeddings` | POST | LLM / 向量 |

**图片**（模型名含 `pro`→`nano_banana_pro`，含 `lite`→`nano_banana_2_lite`，否则 `nano_banana_2`）：
```bash
# 纯文生图
curl -s -X POST http://127.0.0.1:8790/v1/images/generations \
  -H 'Content-Type: application/json' \
  -d '{"model":"nano-banana-pro","prompt":"...","size":"1344x768"}'

# ⭐ 图生图：**图片接口同样吃 reference_images**（2026-09-19 实测通过，做角色/产品还原必用）
curl -s -X POST http://127.0.0.1:8790/v1/images/generations \
  -H 'Content-Type: application/json' \
  -d '{"model":"nano-banana-pro","prompt":"...","size":"1344x768",
       "reference_images":[{"path":"/abs/path/ref.png","name":"ref.png"}]}'
# → {"data":[{"url":"http://127.0.0.1:8790/files/x.jpg","local_path":"~/.hermes/drama-gateway/media/x.jpg"}]}
```

**视频**（模型名含 `omni`/`flash`/`seedance`→`omni_flash`，否则 `veo_31_fast`）：
```bash
# ① 提交
curl -s -X POST http://127.0.0.1:8790/v1/videos/generations \
  -H 'Content-Type: application/json' \
  -d '{"model":"omni-flash","prompt":"...","aspect_ratio":"16:9",
       "duration":6,"resolution":"720p",
       "reference_images":[{"path":"/abs/path/key.jpg","name":"key.jpg"}]}'
# → {"request_id":"glabs-xxxx","status":"running"}
# ② 轮询（每 15s，实测 51–59s 完成）
curl -s http://127.0.0.1:8790/v1/videos/glabs-xxxx
```

**要点**
- `duration` 只认 4/6/8/10；`resolution` 只认 360p/720p/1080p/4K（写成 list）。
- **有 reference_images/reference_videos → 自动走 Omni Flash `components` 模式**；没有 → `text_to_video`。
  两者都**不锁首帧**（符合 Seth 的铁律：不要黑边/僵硬锁定帧）。
- 产物落在 `~/.hermes/drama-gateway/media/`，`local_path` 直接可拷。

**复用脚本 —— spec 驱动三件套**（在 vault `003-Workbench/_build/`，2026-09-19 重构，出图/出片/合成全 spec 化）：
```bash
P=~/.workbuddy/binaries/python/versions/3.13.12/bin/python3
cd $VAULT_PATH/003-Workbench/_build
$P gen_frames.py specs/<x>.json     # 出图（支持 refs → 图生图）
$P gen_clips.py  specs/<x>.json     # 出片（支持 per-clip duration / 额外 refs）
$P assemble_reel.py specs/<x>.json  # 合成（xstack 式 xfade 链 + 免费 drone + loudnorm）
```
spec 都用同一套字段（`out_dir` / `shots` 或 `frames`/`clips` / `xfade` / `drone`），**换参考只改 JSON，不写新脚本**。
旧的 `gen_keyframes.py` / `gen_videos.py` / `assemble_replica.py` 是 Emanation 专用版，保留可用。

**spec 驱动的额外能力**
- ref 传递按后端分：`--backend native`（默认）走 **base64**，**不碰磁盘 → vault 里的图可直接用**；
  `--backend gateway` 没有 base64 通道，脚本会先复制到 `~/.hermes/drama-gateway/media/` 再提交（绕 TCC）。
- `gen_clips.py` 支持 per-clip `duration`，用不同长度镜头凑总时长（例：3×6s + 2×8s + 0.8s xfade ×4 = **正好 30.0s**）。
- `assemble_reel.py` 用 `n` 个输入做 xfade 链，总时长 = `sum(len) - xfade*(n-1)`，脚本自己算。`drone: null` 则不加低频底噪（品牌片/节奏片应该关掉）。
- `assemble_reel.py` 有可选 **`scale`** 键（默认 `1280:720`）。**源是 360p 就写 `"640:360"`**，别让它假装成 720p。
- ⭐ `assemble_reel.py` 有可选 **`music`** 键（**外部音乐轨**，2026-09-20 加）：
  `{"path","start","gain","fade_in","fade_out","amb_duck"}` —— 自动裁到片长 → 淡入淡出 →
  **环境声压到 `amb_duck`（例 0.35）给音乐让位**（简易 ducking）。
  **文件不存在时跳过并警告**（画面照常出）→ 可以先出画面、再补音乐，重跑一次 spec 即可。
- ⭐ `assemble_montage.py` 是**快节奏**专用（硬切 + punch-in + 每刀脉冲音）。**慢片走 reel，快片走 montage。**
- `resolution` 支持 **360p**，Seth 常用它省额度（实测 640×360 / 24fps，出片 48–52s/条）。

⭐ **定格（stop motion）画风：两招已验证**（2026-09-19 实测，见 vault `Wiki/Research/Behance-定格画风实测-2026-09.md`）
1. **画风提示词**：`handcrafted miniature diorama set built for a stop-motion film` +
   列出**手作材质**（foam board / card / balsa / wool / felt，笔触、卡纸毛边、胶痕）+
   **暖色实用光** + **深蓝夜色** + ⭐**品红/青霓虹点缀** + 倾斜景深 + 微距。
   ⚠️ 最容易漏的是**霓虹色板** —— 文字说不清，**必须给参考图**才能锁住。
2. **顿帧（12fps）不要指望模型** —— 后期一行就有，零成本、可控：
   ```bash
   ffmpeg -i reel.mp4 -vf "fps=12" -c:v libx264 -crf 18 -c:a copy reel-12fps.mp4
   ```
   若要模型自带顿帧，prompt 加 `frame-by-frame stepping, like 12fps puppet animation`
   （实测室内镜 53% 帧为静止帧、瞬时跳变 16.1，确有 stepping 特征；但**不稳定，别当依赖**）。

⚠️ **出片会被安全过滤静默挡掉（2026-09-19 踩到）。**
症状：任务直接失败，报错只有 `error_code=0 DANGEROUS DANGEROUS`（`gen_clips.py` 打印 `任务失败 error_code=0 DANGEROUS DANGEROUS`），
**不告诉你是哪一句**。
中招的写法（描述「疲惫 / 结束 / 静止」时）：
`dying lamp` · `one small final movement` · `go completely still` · `lies slumped face-down`。
改成中性描述一次通过：`rests quietly` · `his heavy eyes closed` · `calm and peaceful end of a long day`。
→ **命中过一次就记下来，别重复踩。** 重跑只需再执行一次同一 spec（脚本幂等，只跑缺的那条）。

**凑整时长**：`duration` 只认 4/6/8/10，所以是**挑 xfade** 让 `目标 + xfade×(n-1)` 落在可用组合上。
例：**5 镜正好 30.0s** → `xfade=1.0` 需片段和 34 = **6+6+6+8+8**（实测 30.000s）；`xfade=0.5` → **6+6+6+6+8**。
（⚠️ `3×6s+2×8s` 配 xfade 0.8 是 **30.8s**，不是 30.0。）

⭐ **两张参考图可叠加，各管一件事**（2026-09-19 C1 实测）：
**角色 ref 保身份，风格 ref 保色板，互不干扰。** 别担心「多一张风格图会稀释角色」——实测不会；
该担心的是反向：不给风格图，就拿不到那个色板。

⚠️ **动手前先看图（铁律，三课都付了学费）。**
- 第 1 课（Emanation）：没读参考就写 prompt → **方向**写错（写成「暗底抽象几何」，实际是白色神殿+哑光球+水镜+绿蕨）。
- 第 2 课（Mectron）：只看标题就判类型 → **连「这是什么类型的项目」都判错**（标成「产品片」，实际是牙科品牌吉祥物动画短片）。
  类型判错 → 技法、成本、风险点全错。
  **升级版：动手前必须有画面级证据（项目详情 + 至少 2 张图）；标题和封面都不算数。**
- 第 3 课（SYG，最贵的一课）：**prompt 与参考图不能互相打架。**
  Mectron 那轮我 prompt 写「blue dinosaur」，参考图实际是一只**巨型牙齿**（作者 tag 写 Dinosaur 误导了我）——
  两个信号在拉扯，**一半的漂移是我造成的，不是模型的锅**。
  **正确做法：把参考图里每个特征逐条列出来，prompt 只写你亲眼看到的。**
  名字 / tags / 标题都可能骗你，只有画面算数。
- 顺带结论：**参考图不是可选项。** 同一句 prompt，有 / 没参考图，输出完全不同质量
  （A/B 实测：`mectron-run.html` 角色还原 = 负面案例；`syg-run.html` 画风迁移 = 正面案例）。
- ⭐ **任务性质决定成败**：**风格迁移（「像那一类」）AI 很行；角色还原（「就是那一个」）不行。**
  前者宽容，后者要求身份特征逐条对上。做管线分工时先分清你手上是哪种。

## 启动整个栈（5 个服务）

**一键启动（推荐，无需 WorkBuddy）**: `~/Code/drama-claw-hermes/bin/start-dramaclaw.sh`
检查 5 个服务、缺哪个起哪个、等 health、自动开浏览器到 http://127.0.0.1:8080。桌面 App (G-Labs Studio :8765 / Voice :8766) 只能检测不能启动。日志在 `~/Code/drama-claw-hermes/logs/`。

```bash
# 手动逐个启动（等同一个脚本做的事）
# 1. G-Labs Studio (app, Webhook tab :8765) — 已运行
# 2. G-Labs Voice Studio (app, Webhook :8766, autostart 已开) — 已运行
# 3. DramaClaw API
cd ~/Code/drama-claw && ST_EDITION=ce uv run novelvideo api --port 8780
# 4. drama-gateway  ← ⚠️ 别用裸 nohup &：agent 收尾时会连子进程一起回收，端口就空了
/usr/bin/python3 ~/Code/drama-claw-hermes/bin/daemon-run.py \
  --log ~/Code/drama-claw-hermes/logs/gateway.log --env NO_PROXY='*' \
  -- /usr/bin/python3 ~/Code/drama-claw-hermes/agy-shim/drama_gateway.py --port 8790
# 5. XiaHua 前端
cd ~/Code/drama-claw/frontend && pnpm dev --port 8080
```

**两个新工具（2026-09-19 加）**
- `bin/daemon-run.py` —— 通用「脱钩启动」器（macOS 没有 `setsid`）。double-fork + setsid，
  跟 `nohup cmd &` 的区别是**真的会活过父进程**。任何要在 agent 会话里长期跑的服务都该用它。
  用法：`daemon-run.py --log <file> [--env K=V]… -- <cmd...>`
- `~/Library/LaunchAgents/com.grainyhue.drama-gateway.plist` —— 把 gateway 交给 launchd 常驻
  （RunAtLoad + KeepAlive + 已清代理 + 日志到同一个 gateway.log）。**登录时自动生效**。
  手动启用（在真实终端里跑，沙箱里 `launchctl` 会报 `5: Input/output error`）：
  ```bash
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.grainyhue.drama-gateway.plist
  # 卸载：
  launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.grainyhue.drama-gateway.plist
  ```
  ⚠️ 启用后别再让 `start-dramaclaw.sh` 抢同一个端口（脚本会自己识别「已运行」并跳过，安全）。


## 配置备份 / 恢复（Settings → Backup & Restore 页）

前端 Settings 对话框有第三个页「备份与恢复」(Backup & Restore)，一键把整个 `runtime_settings`（网关 mode/base_url/key、媒体 relay、渠道等）导出为 JSON、或从 JSON 导入恢复（upsert 语义）。底层 API：

```bash
# 导出整个配置（含库中已存密钥；掩码存储的密钥保持掩码）
curl http://127.0.0.1:8780/api/v1/config-backup/export
# 导入（body: {"settings": {key: value}}）
curl -X POST http://127.0.0.1:8780/api/v1/config-backup/import -H 'Content-Type: application/json' \
  -d '{"settings": {"model_gateway_mode": "custom"}}'
```

后端在 `src/novelvideo/api/routes/config_backup.py`（格式版本 1，key 上限 1000，非对象/超限回 400）。前端查询 `frontend/src/lib/queries/config-backup.ts`。已 push 到 sethliao/dramaclaw `seth-patches` 分支。

## 密钥（自动读取）
- G-Labs Studio key: `~/.hermes/.glabs_key`（gateway 自动读）。真源在
  `~/Library/Application Support/G-Labs Studio/webhook_config.json`；app 改名/重置后跑
  `glabs.py key --sync` 同步。
- Voice Studio key: 自动从 `~/Library/Application Support/G-Labs Voice Studio/settings.json` 读
- SiliconFlow/DeepSeek: `~/.hermes/.env`（gateway 自动 load）

## 标准 pipeline 顺序（API 直接驱动，2026-09-02 实测）
```
ingest/upload + ingest/start(rebuild) → build_characters → episodes/plan →
episodes/N/identities/plan → script/generate → episodes/N/rewrite/generate →
scenes/plan → props/plan → portraits(portrait-async, 队列上限~3) →
sketches/generate → beats/{b}/video-prompt/generate → beats/{b}/video →
audio/generate → videos/compose
```

### 铁律/坑（实测）
- **Ingest brief 必须是剧本格式**（场景头 + `角色: 台词` 对白行），纯小说散文会被降级成 1 个"黑屏标题" beat，且 scenes/plan 报"未识别到任何场景，请先生成逐行解说工作稿"。
- scenes/plan 依赖 **adapted-content**（逐行解说工作稿），必须先跑 `episodes/N/rewrite/generate`（POST，body `{"target_beats":12,...}`）生成它。
- video-prompt/generate 依赖 sketch 或首帧已存在；所以顺序是 sketches → video-prompt → video。
- **角色 face_prompt 必须显式含 `round plush 3D toy` + 动物描述**；角色提取自动生成的 face_prompt 会写"儿童/未知性别"导致肖像生成**真人小孩**（违反"全动物拟人"铁律）。鸟类/鲸类要额外加 `fully animal stuffed toy with no human face` 才避免人形化。改 face_prompt 后需重新 portrait-async。
- **音频截断（09-02 Paikea EP1 实测）**：TTS 台词若长于 beat 视频时长（默认 4s），compose `-shortest` 会截断音频。**先生成音频再定视频时长**：量每个 beat 的 audio duration，视频时长取 ceil 到 4/6/8/10（Omni Flash 支持档位）并留 >0.3s 余量（beat 8 台词 6.24s 用 6s 仍截，须 8s）。
- portrait-async 每项目 default 队列并发上限约 3，多了报"队列任务已满"，排队等前批完成。
- MCP launcher 的 DRAMACLAW_API_URL env 在部分 session 不生效（报 not set）→ 直接用 curl http://127.0.0.1:8780 驱动；注意 path 要带 /api/v1/。
- 项目名只允许字母/数字/下划线；URL 里用 project ID 不是 display name。

## DramaClaw MCP（Hermes 可用 34 个工具）
- 已注册: `hermes mcp add dramaclaw --command ~/Code/drama-claw-hermes/bin/drama-mcp-launcher.sh --env DRAMACLAW_API_URL=http://127.0.0.1:8780 --env DRAMACLAW_CE_OWNER=1`
- launcher: `~/Code/drama-claw-hermes/bin/drama-mcp-launcher.sh`（cd 到 repo 再 uv run）
- 工具: dramaclaw_build_characters / generate_script / generate_portrait / generate_sketches / render_first_frames / start_single_video / generate_audio / compose_episode / get_final_video + 通用 get/post/patch/delete
- 生成是异步的: 调工具 → 返回 task → poll dramaclaw_pipeline_status / list_tasks / get_task
- ⚠️ MCP 工具按 session 加载 — 新注册后要开新 session 才有
- 配 gateway 后，MCP 的图片/视频/音频会自动走 G-Labs + Voice Studio

## 配置 DramaClaw 指向 gateway
```bash
/usr/bin/python3 ~/Code/drama-claw-hermes/bin/drama-gateway-config.py          # 指向 :8790
/usr/bin/python3 ~/Code/drama-claw-hermes/bin/drama-gateway-config.py --status  # 查看
/usr/bin/python3 ~/Code/drama-claw-hermes/bin/drama-gateway-config.py --reset   # 回 official
```

## 直接调 gateway（不经 DramaClaw）
```bash
# 图片 (参考图用 reference_images 传 URL/data/local)
curl -X POST http://127.0.0.1:8790/v1/images/generations -H 'Content-Type: application/json' \
  -d '{"model":"nano-banana-2","prompt":"...","size":"1024x1024","reference_images":[{"url":"..."}]}'
# 视频 (components 模式, 360p 草稿便宜)
curl -X POST http://127.0.0.1:8790/v1/videos/generations -H 'Content-Type: application/json' \
  -d '{"model":"omni-flash","prompt":"...","reference_images":[{"url":"..."}],"aspect_ratio":"16:9","resolution":"360p","duration":4}'
# → request_id → GET /v1/videos/{request_id} 轮询到 done → video.url
# TTS
curl -X POST http://127.0.0.1:8790/v1/audio/speech -H 'Content-Type: application/json' \
  -d '{"input":"text","voice":"fac_fe58f702","response_format":"wav"}' -o out.wav
```
产物在 `~/.hermes/drama-gateway/media/`，/files/{name} 可访问。

## TTS 声线切换与控制台
- 默认 TTS = **edge_tts 免费男声 `zh-CN-YunjianNeural`（云健）**；备选 `volc_tts`（火山 doubao-seed-tts-2.0, ARK_API_KEY 在 ~/.hermes/.env）
- Voice Studio App **已删（2026-09）** — 不影响 TTS，网关直接走 API
- 换声线/后端：编辑 `~/.hermes/drama-gateway/providers.ini` 的 `[audio]` 段（provider= / voice=），或
  `bin/drama-tts.sh status|list|set <voice>|provider <name>|test [文本]`（自动重启 gateway）
- 预检控制台: `bin/drama-panel.py` → http://127.0.0.1:8899（服务状态 / 一键启动 / 换声线 / 试听，纯 stdlib）
- 桌面快捷方式: `~/Desktop/Start DramaClaw Stack.command`（双击 = 全家桶 + 控制台 + 浏览器，无需 Hermes）
- ⚠️ 改 providers.ini 的 [audio] 后 gateway 需重启才生效（脚本/面板会自动重启）

## 编码协作
- Seth 希望 drama-claw / hermes 的编码任务尽量走 **agy -p（Antigravity CLI）**，消耗其 Antigravity 订阅额度（`agy -p` 已验证可用）。部署 / 重启 / 验证仍由 Hermes 负责。

## 更新 fork 且保住本地 patch（token-light 法）

当 upstream (dramaclaw/dramaclaw) 更新，本地有自定义 patch（如 `video_generator.py`、`identity_planner.py` 改动）时要同步：

```bash
cd ~/Code/drama-claw
# 1. 先确认本地改动是否已提交/暂存（merge/rebase 前必须干净）
git status --short        # 若有改动：git stash push -m "wip" 或 git commit
# 2. 拉取上游（quiet，不 dump 文件列表进 context）
git fetch upstream --quiet || git remote add upstream https://github.com/dramaclaw/dramaclaw && git fetch upstream --quiet
# 3. 用 rebase 而非 merge —— 把你的 patch 重放到 upstream 之上（无 merge commit，冲突列表更小）
git rebase upstream/main
#    └─ 冲突时只列冲突文件：git status --short | grep '^UU'
# 4. 需要手动解冲突时，git 输出一律重定向到文件，别让它进对话 context：
git rebase upstream/main > /tmp/rb.log 2>&1; grep -c CONFLICT /tmp/rb.log; grep -n '^UU' /tmp/rb.log
# 5. 解完：git add <files> && git rebase --continue
# 6. 若冲突复杂想保留当前状态：git rebase --abort 回滚

# 备选（不想 rebase，只想先存当前状态）
git stash push -m "before-upstream-update" && git merge upstream/main > /tmp/m.log 2>&1 && git stash pop

# ⚠️ 规则：git 的 diff/merge/status 输出是给文件看的，不是给对话 context 看的。
#    大输出一律 > /tmp/xxx.log 2>&1 然后只读汇总行（grep count / tail）。
#    严禁让 agent 直接 cat 整个 merge 输出（上次 20K chars 文件列表烧了一堆 token）。
```

## 已验证（2026-08-30）
- DramaClaw CE :8780 跑通 (ST_EDITION=ce)，281 routes，/healthz ok
- gateway 四腿全通: chat→agy `GATEWAY_OK`; image→G-Labs 1024×1024; video→G-Labs 640×360 4s mp4 (components); audio→Voice Studio 24kHz WAV
- DramaClaw freezone/gen API → gateway → G-Labs 图片落盘到项目（M1e 端到端）
- MCP 34 工具注册成功 (新 session 生效)
- Momo the Panda 测试: 角色sheet + 2 场景图 + 2 视频clip（含 components 模式）

## Pitfalls
- **🔴 本机回环被代理劫持**：环境带 `HTTP_PROXY=127.0.0.1:5xxxx`，curl/urllib 默认把它用在 127.0.0.1 上 → 全部 502 `upstream connect failed: Connection refused (os error 61)`。curl 加 `--noproxy '*'`；Python 传 `NO_PROXY=*`。**看到 `os error 61` 先想代理，别急着重启服务。**
- **🔴 app 改名 = key 重置**：G-Labs 的 key 存在 app 自己的 `webhook_config.json` 里，app 改名/重装会换 key，而 `~/.hermes/.glabs_key` 不会自动跟 → 全链路 401（**静默失败，不报错**）。修：`glabs.py key --sync` + 重启 gateway。
- **🔴 裸 `nohup … &` 起 gateway 会被回收**：agent/终端收尾时会连子进程一起杀，端口悄悄空掉。用 `bin/daemon-run.py`。
- **参考图绝不放 TCC 保护目录**（~/Documents/, ~/Desktop/, ~/Downloads/）— G-Labs 上传 ref 会报 `UPLOAD_ERROR Operation not permitted`（macOS 隐私）。放 ~/.hermes/ 或 ~/GrainyHue/ 等非保护路径。若必须用 vault 图，先 cp 到 ~/.hermes/drama-gateway/media/ 再提交。**更新解法：改用 `glabs.py --ref-mode base64`**（默认），图片编码进请求体，app 完全不碰磁盘 —— 2026-09-19 实测通过。永久解法：系统设置→隐私与安全性→文件与文件夹→G-Labs Studio→开 Documents
- **项目名只允许字母/数字/下划线**（GUI 和 API 都校验，连字符会拒）— 新建项目 GUI 的确认按钮会在非法名时保持 disabled
- `ST_EDITION=ce` 必须显式设，否则拒绝启动（缺 control-plane DSN）
- 首次跑 `uv sync --group dev`；前端用 `pnpm install` + `pnpm dev`
- gateway 是 stdlib-only 单文件，blocking 调用跑在 to_thread（别改回 run_until_complete）
- 视频绝不用 first_frame/start_end（Seth 明确要求）— components 参考图
- Voice Studio 冷启动要 ~30s 加载模型才起 webhook
- DramaClaw 深度 pipeline 需先 ingest 小说/故事源 → 身份规划 → 才可剧本
- 产物 URL 用本地时间戳文件名（gateway /files/），不是 G-Labs 原始名
