---
name: drama-episode-automation
description: "Use when a brief must become a generated DramaClaw episode."
tags:
  - dramaclaw
  - glabs
  - automation
  - episode
  - brief
agent_created: true
---

# DramaClaw 一键剧集自动化 (Brief → Episode)

## 何时使用
- Seth 给一个 brief / rough story，要自动生成剧集（或整季）
- 需要自动提取风格/对白语言/语气/画幅并应用到生成设置
- Hermes 编排 DramaClaw 全流程（34 个 MCP 工具），Seth 在 Web UI (:8080) 审查/编辑

## 已验证端到端（2026-08-31/09-01, momo_ep2_test）
- EP001/EP002（包子与汉字/灯笼的误会）+ **EP003（奶奶的家书, 34.7s）** 全流程跑通
- EP3 一致性验证通过（vision 抽查 3 个 shot）：同一间奶奶家客厅（木质家具/红灯笼/书法字画），5 只动物角色全部正确出场——单账号 pin + scene_id 修复 + style bible 生效

## 环境/账号一致性（Seth 2026-09-01）
- **G-Labs 双账号会导致风格漂移**：openai_accounts.json 有两个 enabled 账号（grainybloomstudios / krhmqpgf），webhook 可能轮换。修法：providers.ini [glabs] 加 `account_id = 0d385969-...`（grainybloomstudios），gateway 在 image/video payload 里带 account_id；或 Seth 在 G-Labs app Accounts 页禁用多余账号
- **分辨率用 "360p" 字符串**（不是 "640x360"）："640x360" 会被 _seedance2_resolution_for_backend 归一化成 720p；"360p" 正确落到 640x360 输出
- **route 要求 beat 必须有 video_prompt**：PATCH 只设 visual_description 不够，`beats/{n}/video` 会报“缺少视频提示词”；视频 prompt 用动物明示+style bible 手写（别用 LLM 生成的“小男孩/小女孩”）

## 核心原则（Seth 明确要求，不可违反）
1. **先计划后执行**：每部剧先出计划（集数/风格 spec/预计 quota 消耗），Seth 批准后才开始生成
2. **脚本检查点（硬停）**：`generate_script` 完成后必须暂停，让 Seth 在 GUI `episodes/$episode/script` 改完剧本/对白/语言再继续——保护 G-Labs quota（图像/视频才花钱，剧本只有 LLM 成本）
3. **视频只用 components 模式**（参考图=ingredient），**永不用** first_frame / start_end_image（Seth：无黑边/僵硬锁定帧）
3b. **同一部剧所有集必须在同一个 project 里生成**（ingest 完整 brief 含全部集），绝不每集新建项目——否则角色肖像/场景 master/风格无法跨集引用（Seth 2026-08-31 纠正）
3c. **components 参考图=主角肖像+场景 master，绝不放草图**——草图会变成画面锚点，看起来像首帧锁定（Seth 2026-08-31 纠正，beat1 视频就是草图印在里面）
3d. **所有出场角色肖像都要发**（不要只发主角）——只发一个角色时，其余角色会被模型自由发挥成错角色/真人小孩（Seth 2026-09-01 纠正；上限 6 张）
3e. **画幅=横屏 16:9**（Seth 2026-09-01 纠正；短剧项目 aspect_ratio 16:9，视频请求 resolution 640x360；components 模式 frame_path=None 时 _resolve_video_aspect_ratio 会回退 9:16，路由必须显式传 config["ratio"]=项目 aspect_ratio）
3f. **全动物拟人，绝无真人小孩**：视频 prompt 必须显式写 "anthropomorphic animal characters only, no humans, no human children"；LLM 生成的 video-prompt 会写成“小男孩/小女孩”，需手工改写或强 prompt（Seth 2026-09-01 纠正）
4. **参考图绝不放 TCC 保护目录**（~/Documents/ ~/Desktop/ ~/Downloads/）——先 `cp` 到 `~/.hermes/drama-gateway/media/` 再提交，否则 G-Labs 报 `UPLOAD_ERROR Operation not permitted`
5. **项目名只允许字母/数字/下划线**（连字符会被 GUI/API 拒）
6. 异步任务一律 poll（3–5s 间隔）；`failed` 读 `error_code`/`error`/`error_detail`，重试一次，再失败就停下报告

## 环境（5 服务，先确认全活着）
| 服务 | 地址 | 健康检查 |
|---|---|---|
| G-Labs Automation | 127.0.0.1:8765 | `GET /api/health` |
| G-Labs Voice Studio | 127.0.0.1:8766 | webhook 就绪 |
| DramaClaw CE | 127.0.0.1:8780 | `GET /healthz` |
| drama-gateway | 127.0.0.1:8790 | 任意 /v1 调用 |
| XiaHua 前端 | 127.0.0.1:8080 | `GET /` 200 |

启动命令见 `drama-claw-hermes` skill（ST_EDITION=ce、gateway stdlib-only 单文件）。直接调 API 用 header `X-CE-Owner: 1`；MCP 工具每次都要显式传 `project_id`（环境变量 DRAMACLAW_PROJECT_ID 未设）。

## 风格自动生成（brief → style spec → 应用）
1. LLM（Hermes）从 brief 提取 style spec（JSON）：`visual_style`（视觉风格）、`art_direction`（美术方向）、`palette`（色调）、`dialogue_language`（对白语言，如 zh/en）、`tone`（语气）、`aspect`（画幅：短剧 9:16 / 横屏 16:9）、`duration`（每集目标时长）
2. `GET /api/v1/styles?project={project}` 看预设风格的字段格式（复制 schema）
3. `POST /api/v1/styles` 创建自定义风格（body 参照预设字段 + 上述 spec）；若 400，先 GET 现有自定义风格 debug 再重试
4. 应用到项目：查项目记录找 style 字段（`GET /api/v1/projects`），用 `PATCH /api/v1/projects/{id}` 或对应端点设置；不确定就让 Seth 在 GUI styles 页确认
5. 画幅设定同步影响 G-Labs 视频调用（`aspect_ratio` 9:16 / 16:9）
6. 备选：Seth 提供参考图时走 `POST /api/v1/projects/{project}/styles/analyze`（multipart 文件，AI 反推风格参数）

## 流程（MCP 工具链，每步校验产物）
```
0. 计划 → Seth 批准（集数/风格 spec/预计 quota）
1. 项目：GET /api/v1/projects → 复用或 POST 新建（名字合规）
2. 素材：brief/小说 → ingest（前端 ingest 页上传，或 API；GET list_ingest_uploads 确认）
3. 风格：按上文风格自动生成 → 应用
4. plan_episodes（异步 build task → poll 到 done）
5. 每集：
   a. plan_identities → poll
   b. generate_script → poll
   c. ⏸ 硬停：Seth 在 GUI 改剧本（语言/对白/分镜描述）→ 确认继续
   d. plan_scenes → plan_props → build_characters
   e. generate_portrait（或 generate_identity_image）→ generate_scene_master
   f. generate_sketches → detect_sketch_identities（修 face_prompt 若需要）
   g. render_first_frames → start_single_video（每 beat，components 模式）
   h. generate_audio（Voice Studio via gateway）
   i. compose_episode → optimize_video_global → get_final_video
```
轮询一律 `dramaclaw_get_task` / `dramaclaw_list_tasks` / `dramaclaw_pipeline_status`；Seth 可在 GUI tasks 页实时看进度。

## 产物校验清单
- 剧本：`dramaclaw_get_episode_script` 有内容（scene/beat 结构完整）
- 角色：`get_character_media` 出 portrait/identity 图 URL
- 分镜：`get_sketches` 每 beat 有候选图；`get_first_frames` 出首帧
- 视频：`get_episode_media` 每 beat 有 video（360p 草稿 → 通过后再 720p）
- 合成：`get_final_video` 返回可播放 URL
- 产物 URL 是本地时间戳文件名（gateway /files/），不是 G-Labs 原始名

## Quota 控制（G-Labs 共享 Google quota）
- 草稿阶段用 360p（仅 Omni Flash 支持）或先少 beats；定稿才 720p/1080p
- 4K / veo_31_lite_relaxed / Veo 4s·6s 需要 ULTRA 账号；Omni Flash 不需要 ULTRA
- 每阶段开始前向 Seth 报预计消耗，他点头才继续（尤其 start_single_video 批量那步）

## 已验证端到端（2026-08-31, momo_ep1_test）
全链路 brief→成片跑通（G-Labs 本地, 零云中继）：
- 项目→ingest→build_episodes→build_characters→identity_planner→script→scenes→portraits→scene_master→sketches→render→per-beat video→compose=ep001_final.mp4 ✅
- 中间修了 4 个集成坑（全部记入下方 Pitfalls/协议）
- **启动后端必须带** `GATEWAY_LOCAL_RELAY=1`（否则 Cloudinary 401）
- 视频最终用“视频内置音轨”合成（无 narrator 也可出片）；TTS 配音被 Voice Studio 403 挡（需付费 plan）

## DramaClaw×gateway 媒体协议（backend 客户端要求）
- **图片 submit**：`POST /v1/images/generations|edits` → 返回 `data[].url`（本地 /files/）
- **视频 submit**：`POST /v1/video/generations`(或 /videos) → 响应必须带 `task_id`（或 id）——gateway 已回 `{request_id, task_id, id, _newapi_request_id, status:running}`
- **视频 poll**：`GET /v1/video/generations/{task_id}`(或 /videos/) → 完成时 `status` ∈ {done,completed,succeeded,success} 且顶层带 `result_url`/`url`/`video_url`（backend `_extract_video_url` 只读顶层/result_url/metadata；不读嵌套 video.url）
- **参考图**：gateway 接受同机绝对路径或 http（`_resolve_ref`）；components 模式必须带参考图，否则 G-Labs 报错
- **模型映射**：seedance*→omni_flash（便宜草稿）；分辨率 360p 最省

## CE 源码 patch（fork 必须带过去）
1. `nanobanana_grid.py` `_relay_reference_images_for_newapi` upload_all(): `GATEWAY_LOCAL_RELAY=1` 时写本地 refs 目录返回路径（跳过云中继）
2. `video_generator.py` `_relay_media_input`: 同款 local relay 短路
3. `identity_planner.py` Pass A/B task prompt 顶部字段说明（defaults/requirements）
4. **模型命名诚实化**（2026-08-31, 全部验证）：
   - `config.py`: NEWAPI_IMAGE_MODEL/NEWAPI_NANOBANANA2_MODEL 默认 "glabs-nano-banana-2"（原 LingShan-G2/NB-2）；IMAGE_GENERATION_SELECTIONS label → "Google Flow Nano Banana 2 (G-Labs)"；NEWAPI_VIDEO_MODELS 列表头插 "glabs-omni-flash"；NEWAPI_VIDEO_DURATION_BOUNDS 加 "glabs-omni-flash:4-10"
   - `schemas.py`: VideoGenerateRequest/SingleVideoRequest 默认 video_backend → "newapi_glabs-omni-flash"
   - `video_generator.py`: NEWAPI_VIDEO_DISPLAY_LABELS 加 "glabs-omni-flash": "Google Flow Omni Flash (G-Labs)"
   - 项目配置: PATCH video_backend=newapi_glabs-omni-flash, sketch_image_selection=newapi_nanobanana2；/video-backends 下拉已显示 "Google Flow Omni Flash (G-Labs) | default"
   - 网关模型映射: seedance*→omni_flash, (omni|flash|seedance)→omni_flash；图片 model 名含 pro/lite → nano_banana_pro/lite，否则 nano_banana_2
5. **indextts2_fal.py egress 放行**（2026-08-31）: `generate()` 里 endpoint 为 127.0.0.1/localhost 且 provider==newapi 时 context=None（跳过组织 egress/计费闸门）——否则 CE 的 IndexTTS2 音频路径必报 ORG_EGRESS_DENIED
6. **components 视频模式（草图→Omni ingredients，2026-08-31）**：Seth 要求“不要首帧/尾帧，用 Omni 模型引用角色直接生成视频”。
   - `schemas.py` SingleVideoRequest 新增 `use_sketch_references: bool = False`
   - `generation.py` beats/{n}/video 路由：`use_sketch_references=true` 或 beat.video_mode=="components" 时跳过首帧 gate，`_build_beat_component_references()` 组装参考图（主角肖像 `assets/characters/{name}/portrait.png` + 场景 `assets/scenes/{name}/master.png`——**不放草图**），video_mode="components"、frame_path=None、config["references"]=refs
   - 生成器侧 has_multimodal_refs → params.update(reference_params) → reference_images → gateway components（已验证 3 图 refs 可解析）
   - 调用例：`POST …/beats/{n}/video {"video_backend":"newapi_glabs-omni-flash","use_sketch_references":true}`
7. **gateway Provider Registry**（2026-08-31）: providers.ini（~/.hermes/drama-gateway/）驱动上游；模型名 `provider:model`；已含 glabs/deepseek/siliconflow/voice_studio/volc_tts；_provider_http 通用请求 + _provider_key（key_env/key_file/key_source）；image/video 仅 glabs 实现（其他 501），audio 支持 volc_tts + voice_studio，chat/embedding 走 openai_compat

## 剩余阻塞（下次继续）
- ~~TTS 配音~~ ✅ 2026-08-31 已通：Volc Ark Agent Plan doubao-seed-tts-2.0（见下方 Volc TTS 段）；compose 已用“独立音频”合旁白
- 更深：Volc seed-tts 是 preset speaker（非克隆）；旁白参考图只是满足 prereq，实际音色来自 preset。后续若要角色专属音色：给每角色一个 speaker，或研究 Volc 克隆接口

## Volc Ark TTS（Seth 已订阅 Agent Plan, 2026-08-31 启用）
- 模型: doubao-seed-tts-2.0；HTTP: POST https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional
- 请求头: `X-Api-Key: <专属key>` + `X-Api-Resource-Id: seed-tts-2.0`（不是 Bearer!）
- 响应: NDJSON 行，每行 `{"code":0,"data":"<base64 音频块>"}`；code==20000000 结束
- Key: ARK_API_KEY 存于 ~/.zshrc + Hermes 环境配置（已持久化）；providers.ini 里 [volc_tts]
- gateway /v1/audio/speech 默认路由 volc_tts（无 key 回退 Voice Studio）；`_handle_volc_tts` 已实现
- DramaClaw 侧全流程: narrator-voice/upload（先 TTS 合成样本）→ audio/billing-quote（prereq 清空）→ audio/generate（IndexTTS2 客户端 → gateway /audio/speech → Volc）→ compose 用独立音频

## Pitfalls
- **compose 默认输出竖屏 720x1280**（Seth 2026-09-01 纠正）：横屏项目必须显式传 `{"resolution":"1280x720"}` 给 `videos/compose`，否则即使 beat 全是 16:9 成片也变竖屏
- **视频时长会被音频时长顶上去**（Seth 2026-09-01 碰壁）：路由 `video_duration = max(请求时长, ceil(audio_duration))`——提交视频时若 audio 还是旧的长旁白，6s 请求会变 8/9/10s；gateway 对不在 {4,6,8,10} 的时长回退 4s（9→4s）。**顺序：先改旁白→再生音频→再生成视频**。compose 会把每个 clip 裁到音频长度（无死白），成片≈音频总长
- **一致性三件套**（Seth 2026-09-01）：1) 每 shot 参考**所有**出场角色肖像；2) prompt 用 style bible——角色/灯笼等描述逐字重复（"identical round red paper lanterns with gold tassels"），全 4 角色每 shot 都在场（Momo 永不消失）；3) 衔接句 "Same lantern street, same four friends continuing from the previous shot"。短 clip(6s) < 长 clip(10s) 一致性好
- **GUI 前端重启**：`cd ~/Code/drama-claw/frontend && npm run dev -- --port 8080`（:8080 常被杀，Seth 要在网页看成片时先拉起）
- **scene_ref 必须用 `scene_id` 字段，不是 `name`**（2026-09-01 大坑）：PATCH beat `{"scene_ref":{"scene_id":"<场景名>"}}`；`name` 会被 SceneRef 静默丢弃 → scene_ref 恒为 null → 场景 master 参考从不发送 → 单 shot 环境漂移（beat3 变纯色背景）。`_build_beat_component_references` 已改为读 scene_id（兼容 name）
- **场景 master 放参考图第一位**（环境锚点优先，防环境漂移）
- **原始模型音轨版本**：compose 优先用独立音频（Volc mp3）；要原始模型音轨（Omni Flash 内置），先把 `audio/ep{NNN}/` 目录临时 mv 走再 compose，完事 mv 回
- **G-Labs 账号自动停用**：报错 "No active accounts available" = G-Labs app Accounts 页 Google 账号掉线，需 Seth 在 app 里重新启用（反复出现，2026-08/09 多次）
- **4s 太短，对白/表演剪不完（Seth 2026-09-01）**：Omni Flash 支持 4/6/8/10s；对白/表演 beat 用 10s，短 message card 用 8s。G-Labs 10s 任务偶发超时（"Task timed out (no completion signal received)" = G-Labs 侧，重试即可）；后端 max_polls=120×5s=600s 轮询够用。旁白文本按 ~4.5 字/s 估算，10s ≈ 45 字，超出就精简旁白（别把长旁白硬塞进 10s 视频）
- **启动后端必须 `GATEWAY_LOCAL_RELAY=1`**，否则图片/视频参考图走 Cloudinary 云中继 → 401
- **gateway LLM 必须 DeepSeek-primary**（agy 是 agent CLI，headless 会因工具权限拒绝而无输出）。已修复: `_load_env_file()` 必须在读取常量**之前**执行（否则 DEEPSEEK_API_KEY 为空）；DeepSeek 不支持 `json_schema` 只支持 `json_object`（gateway 翻译 + 最后一条消息追加 "直接输出 JSON 无代码块" 指令）；缺省 max_tokens=8192、temperature=0.2 防截断
- **PydanticAI 结构化盲区**：CE 有时不随请求发 response_format（rf=null），模型不知道顶层字段名 → 容器字段有 default 时静默解析为空（如 `defaults=[]`）→ "覆盖不完整" 报错。修法：在 drama-claw 源码 identity_planner.py 的 Pass A/B task prompt 里写明顶层字段必须为 `defaults`/`requirements`（本地 CE checkout 已 patch，fork 时要带过去）
- **视频 submit/poll 协议不匹配**（gateway Grok 形状 vs backend newapi 客户端）：gateway 已对齐（task_id + 顶层 url），见上方协议段
- MCP 工具按 session 加载：新注册 MCP 后要开新 session 才有 34 个工具
- MCP 调用必须传 project_id（env 未设 DRAMACLAW_PROJECT_ID）
- 剧本/身份规划走 backend LLM → gateway → agy/DeepSeek，几乎零成本；图像/视频才烧 G-Labs quota
- Assistant surface（虾导）在 CE 不可用（product-surfaces/me available=false）——自动化只能走 Hermes MCP，不能指望 App 内 AI 助手
- 若 API 直接 POST 失败，先 `curl GET /api/v1/projects` 确认项目 id 格式（id 是 ULID，不是名字）
