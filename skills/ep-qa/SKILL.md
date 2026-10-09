---
name: ep-qa
description: 交付前给成片做机器体检 —— 查画幅、时长、音轨、响度、镜头密度、首尾黑帧、帧率、编码，外加同系列一致性对比。只报可测量的交付事实（能不能播、有没有声音、系列齐不齐），⛔ 不判审美。当用户说「体检一下这些片」「这些成片能不能发」「EP1 到 EP4 画幅一致吗」「这条片子有声音吗」「成片质检」「导出完帮我查一下」时使用。零依赖，只调 ffmpeg/ffprobe，不花钱。
agent_created: true
---

# 成片体检器 ep-qa

## 什么时候用

- 一批成片导出完，**发之前**想知道有没有硬伤
- 问「EP1 到 EP4 规格一致吗」
- 怀疑某条片没声音 / 有黑屏 / 画质太低
- 交付前留一份机器可读的质检记录

⛔ **不要用它判审美。** 节奏快慢、构图、颜色、角色像不像 —— 全部归用户。
它只报可测量的交付事实。

## 怎么用

```bash
P=~/.workbuddy/binaries/python/envs/default/bin/python

# 一个系列（推荐 —— 跨文件对比是它最有价值的部分）
$P ep-qa.py --series-dir ~/vault/Assets/某IP/videos --json out.json --html report.html

# 单片
$P ep-qa.py 某片.mp4 --html report.html

# 多文件当成一组
$P ep-qa.py a.mp4 b.mp4 c.mp4 --html report.html
```

退出码：`0` 全过 · `1` 有 WARN · `2` 有 FAIL → **可以直接挂 CI 或 pre-commit hook**。

## 查什么

| # | 项 | FAIL 条件 | WARN 条件 |
|---|---|---|---|
| 1 | 画幅 | 宽高有奇数 | 竖片 / 最长边 < 720 |
| 2 | 时长 | < 3s | > 600s |
| 3 | 音轨 | 没有音频流 | 量不到音量 |
| 4 | 响度 | 平均 < −40dB | 平均 > −6dB / 峰值触顶|
| 5 | 镜头密度 | — | 平均 > 6s / 每分钟 > 60 刀 |
| 6 | 首尾黑 | — | 首或尾帧亮度 < 20 |
| 7 | 帧率 | — | 不稳（VFR）/ < 20fps |
| 8 | 文件 | — | > 500MB / < 0.3MB |
| 系列 | 一致性 | 画幅不一致 | 帧率/编码不一致 / 时长差 > 4 倍 |

阈值在文件顶部常量区，改完**必须重跑负样本**（见下）。

## 🚨 三条硬规矩（都是实测踩出来的，别重踩）

### 1 · ffmpeg 亮度只能这样取

```python
"-vf", "signalstats,metadata=print",   # ⛔ 不要写 metadata=print:file=-
```
- `metadata=print:file=-` 在 ffmpeg 6.1 / Lavf62 下**什么都不输出**（静默失败）
- `metadata=print` 把 `lavfi.signalstats.YAVG=…` 打到 **stderr**
- 输出只搜 stderr。两处都别改，改一处就静默失效。

### 2 · 黑帧阈值不能低于 16

`yuv420p` 是**有限范围**，YAVG 理论下界 = **16.0**（纯黑）。
阈值写 12 → **永远抓不到任何黑帧**。用 20（正样本实测 36~171，有安全间距）。

### 3 · 自检：某指标对所有样本同值 = 这一项没在工作

跑完会检查每个数值指标在样本间有没有变化。**全一样就是没在工作**
（要么静默失败，要么退化成常数）。报出来的时候要**逐个核实** ——
有可能是真的同值（比如同一素材的两次导出），不是指标坏了。

## 验证方法（改任何阈值前后都要做）

**造已知坏的负样本，看它抓不抓得到。「没报」和「没问题」长得一模一样。**

```bash
# 无声
ffmpeg -i in.mp4 -an -c:v copy N1-无声.mp4
# 超短
ffmpeg -i in.mp4 -t 1.5 -c copy N2-超短.mp4
# 极低音量
ffmpeg -i in.mp4 -af "volume=-45dB" -c:v copy -c:a aac N3-极低音量.mp4
# 低清
ffmpeg -i in.mp4 -vf "scale=320:180" -c:v libx264 -crf 40 N4-低清.mp4
# 开头黑
ffmpeg -f lavfi -i color=c=black:s=1280x720:d=2:r=24 -i in.mp4 \
  -filter_complex "[0:v][1:v]concat=n=2:v=1" -c:v libx264 -crf 24 -c:a aac N6-开头黑.mp4
```
6 个负样本（再加一个全坏）→ 期望 **6/6 抓到，正样本零误报**。
⚠️ **改阈值后必须重跑负样本** —— 改阈值不重验 = 把没验过当成验过了。

## 批处理时的坑

- ⚠️ **组名别用 `basename`** —— `A/videos` 和 `B/videos` 都叫 `videos`，
  第二组会**静默覆盖**第一组的json。组名要带父目录。
- ⚠️ `--series-dir` 的 glob **不递归**。子目录里的片要显式列出来。
- ⚠️ 完事之后**核对覆盖数**：`comm` 对比 find 结果和体检结果，0 遗漏才算完。

## 出图后过闸门

```bash
$P $VAULT_PATH/003-Workbench/_build/design_audit.py report.html
```
⚠️ T2 指纹（中间点拼元信息串）**不认内容文本** —— 分组名里用`·` 会被误报。
用 `｜` 或 `／`。**不要为了过闸门去改闸门**，改内容源头。

## 网页验收查渲染后的可见文本

用 `--dump-dom` 拿 DOM → 去 `script`/`style` → 去标签。
⛔ 不要 grep 源码（标题字符串在 `<script>` 里也搜得到，会骗你）。

## 出处与署名

思路借鉴 [OpenMontage](https://github.com/calesthio/OpenMontage)（calesthio，**GNU AGPLv3**）
的 `tools/analysis/visual_qa.py`「渲染后机器自检」。
⚠️ **本工具代码为独立实现，未复制其源码** —— AGPLv3 传染性太强，抄进库不合适。
借鉴的只是「渲染完要机器自检一遍」这个做法。
