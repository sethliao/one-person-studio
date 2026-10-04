# Awesome 一人制片厂 · AI 视频工具地图

> 灵感来自 [awesome-*](https://github.com/sindresorhus/awesome) 生态——但本页不是平铺清单：**按「一个人做出一季动画」的工序组织**，每类先说「我们用哪个、为什么」，再给替代项。
> 商业产品只写定位不写价格（价格变动快，自查官网）；开源项目给仓库链接。持续更新，欢迎 PR。

## ① 生产：从提示词到镜头

| 工具 | 定位 | 我们的状态 |
|---|---|---|
| Agnes Video 2.5 | 长提示词友好、参考图锁角色，官方 API 可批处理 | **主力在用**（有实测：872 字三段式 > 短提示词） |
| Google Veo (Flow) | 质量高、生态成熟，批量走 gflow-cli | 交付通道 |
| MiniMax H3 | 多模态输入（T2VA/I2VA/L2VA/Ref2VA） | 实测过，与 Agnes 互补 |
| Seedance（字节） | 一键成片方向的大厂选手 | 跟踪中 |
| 即梦 / 小云雀类平台 | 面向消费者的「一键出片」 | 跟踪中——多数按会员收费，是否有必要买，见本仓库「别花冤枉钱」系列 |

**我们的一条铁律**：文字/图表/信息图镜头**不要**交给任何视频模型——它会写错字且不可改。这类镜头用 HTML 渲染（可改、可复用、可重跑）。

## ② 质检：片子能不能发

| 工具 | 定位 |
|---|---|
| `ep-qa`（本仓库） | 画幅/时长/音轨/响度/黑帧/帧率/镜头密度/系列一致性，只报可测事实 |
| FFmpeg | 底层兜底，一切格式的最后答案 |

质检阈值得实测标定（例：静音判定 −50dB）。**指标全员同值 = 指标没在工作**。

## ③ 记忆：让系统记得住

| 项目 | 定位 | 链接 |
|---|---|---|
| Markdown 通用大脑（本仓库方案） | 人能读、无锁定，三层记忆 + 链注册表 | [docs/通用大脑.md](../docs/通用大脑.md) |
| second-brain-os | agent 替你维护的纯 Markdown 知识库 | [github.com/undefined-ui/second-brain-os](https://github.com/undefined-ui/second-brain-os) |
| second-brain（Karpathy LLM Wiki 系） | 丢素材 → LLM 编译成 wiki | [github.com/NicholasSpisak/second-brain](https://github.com/NicholasSpisak/second-brain) |
| Mem0 / Letta / Zep | 数据库型记忆层（向量/分页/时序图谱），强在检索 | 自行搜索官网 |

## ④ 调研：把平台变成数据集

| 工具 | 定位 |
|---|---|
| opencli | 160+ 站点适配器，复用已登录浏览器，零 API key |
| `x-bookmarks-mining`（本仓库） | 收藏 → 结构化数据集 → 「按能不能跑」分层看板 |
| `content-research-board`（本仓库） | B站/小红书/抖音/知乎/微博 → 内容调研看板 |
| `behance-research`（本仓库） | Behance 趋势/画像/拆解 |

## ⑤ 同路者（skills 工具箱范式）

| 项目 | 定位 | 链接 |
|---|---|---|
| dbskill | 16,152 条推文 → 4,176 知识原子 → 33 skills，先行者 | [github.com/dontbesilent2025/dbskill](https://github.com/dontbesilent2025/dbskill) |
| agent-bootstrap（本仓库前身） | 一人制片厂的环境恢复仓 | [github.com/sethliao/agent-bootstrap](https://github.com/sethliao/agent-bootstrap) |

## ⑥ 方法论

- **PARA** — Tiago Forte《Building a Second Brain》：本仓库的目录组织思想来源
- **LLM Wiki pattern** — Andrej Karpathy：Markdown 大脑的 wiki 化思路
- **Agent Skills 开放标准**：SKILL.md 即安装单位，任何支持的 agent 通用
