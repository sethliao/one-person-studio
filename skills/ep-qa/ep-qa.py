#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ep-qa.py —— 交付前成片体检器（零依赖 · 只调ffprobe/ffmpeg · 不烧任何额度）

出处 / 署名
----------
想法来自 X 收藏的 OpenMontage（https://github.com/calesthio/OpenMontage，
作者 calesthio，GNU AGPLv3）里的 `tools/analysis/visual_qa.py`：
「渲染后自检ffprobe + 抽帧 + 音频电平 + 字幕」。
⚠️ **本文件是从零自己写的，没有抄它的代码**（AGPLv3 传染性太强，抄进库不合适）。
   借鉴的是「渲染完要机器自检一遍」这个做法，署名在此。

它回答什么
----------
⛔ 不判审美（节奏快慢、构图好不好看 → 归 Seth）。
✅ 只报**可测量的交付事实**：能不能直接发、会不会播不出去、系列之间一不一致。

八项检查
--------
1画幅       宽高比 + 分辨率（系列内不一致 = 直接报）
2  时长     低于 min / 高于 max
3  音轨     有没有音频流
4  电平     三点采样 mean_volume，过低(静音感)/过高(削顶风险)
5  镜头密度  平均镜头时长 + 每分钟切换次数（事实，不是审美判断）
6  首尾黑   片头/片尾是否有近黑帧（观众看到的"黑一下"）
7  帧率     是否恒定（VFR 会让部分平台转码出bug）
8  文件     体积 + 编码

用法
----
    python ep-qa.py <file.mp4> [more.mp4 ...] --json out.json --html report.html
    python ep-qa.py --series-dir<dir> --json out.json --html report.html
退出码：0 全过 · 1 有WARN · 2 有 FAIL
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# ── 阈值（全部有理由，见README「阈值从哪来」）────────────────────────────
MIN_DURATION = 3.0        # 低于 3s 的片子在任何一个平台都没有意义
MAX_DURATION = 600.0      # 10 分钟：再长要切片分发，不该当单条交付
# 🚨 阈值是**实测标定**出来的，不是拍的（2026-10-05 被Seth 纠正过一次）
# 实测样本：他的成片 -19~ -22dB｜Agnes 带参考图那条 -37dB（有环境声）｜
#           Agnes 纯文字那条 -59dB（真的没声）｜
#           莫莫 EP1-4 -21~ -25dB
# ⚠️ 我原来写 -40，把「安静的环境声」误判成「静音」，被告知「我昨天看是有声音的」。
#   **一个明显错误的检查结论比没有这个检查更糟 —— 它会让你扔掉一条好片。**
QUIET_MEAN_DB = -50.0     # 实测：真无声 ≤ -59，有环境声 ≥ -37。-50 在两者之间。
LOUD_MEAN_DB = -6.0       # 平均高于 -6dBFS≈ 长期过载风险
CLIP_MAX_DB = -0.5        # 峰值高于 -0.5dBFS = 已经削顶
BLACK_LUMA = 20.0         #近黑帧。⚠️ 别写 12：yuv420p 是**有限范围**，
                          # YAVG 的理论下界是 16（纯黑就等于 16.0），
                          # 阈值低于 16 的话**永远抓不到任何黑帧**（实测踩过）。
                          # 正样本实测区间 36~171，纯黑 16.0 → 20 有安全间距。
MAX_AVG_SHOT_S = 6.0      # 平均镜头 > 6s 观众容易走神（事实陈述，不是审美）
MAX_SHOTS_PER_MIN = 60# 每分钟 > 60 个镜头 = 高频硬切，平台与眼睛都吃力

# ── ffmpeg / ffprobe ────────────────────────────────────────────────
def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def probe(path: str) -> dict[str, Any]:
    """ffprobe 拿容器/流信息。只用 json 输出，避免解析脆弱的默认格式。"""
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]
    r = _run(cmd)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe 失败: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout)


def _frac_to_float(s: str | None) -> float | None:
    """'24/1' -> 24.0。VFR 的 avg_frame_rate 和 r_frame_rate 会不一致。"""
    if not s:
        return None
    try:
        if "/" in s:
            a, b = s.split("/", 1)
            b = float(b)
            return float(a) / b if b else None
        return float(s)
    except Exception:
        return None


def audio_levels(path: str, duration: float, n: int = 3) -> list[dict[str, Any]]:
    """在 n 个时间点各取 3 秒做 volumedetect。返回 [{ts, mean, max}]。"""
    if n <= 1:
        pts = [max(duration / 2, 0.5)]
    else:
        pts = [duration * f for f in (0.1, 0.5, 0.9)]
    pts = [round(min(max(p, 0.1), max(duration - 0.5, 0.2)), 2) for p in pts]
    out = []
    for ts in pts:
        r = _run([
            "ffmpeg", "-hide_banner", "-nostats", "-ss", str(ts), "-t", "3",
            "-i", path, "-vn", "-af", "volumedetect",
            "-f", "null", "-",
        ], timeout=90)
        mean = mx = None
        for line in r.stderr.splitlines():
            if "mean_volume:" in line:
                mean = _db(line, "mean_volume:")
            elif "max_volume:" in line:
                mx = _db(line, "max_volume:")
        out.append({"ts": ts, "mean_db": mean, "max_db": mx})
    return out


def _db(line: str, key: str) -> float | None:
    m = re.search(re.escape(key) + r"\s*(-?[\d.]+)\s*dB", line)
    return float(m.group(1)) if m else None


def shot_boundaries(path: str, threshold: float = 0.3, min_len: float = 0.5) -> list[float]:
    """镜头切换点。用 lavfi select='gt(scene,thr)' —— 不装 pyscenedetect 也能跑。"""
    esc = str(Path(path).resolve()).replace("\\", "/").replace("'", r"\'")
    r = _run([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_entries", "frame=pts_time",
        "-f", "lavfi",
        f"movie='{esc}',select='gt(scene,{threshold})'",
    ], timeout=180)
    pts: list[float] = [0.0]
    try:
        for fr in json.loads(r.stdout).get("frames", []):
            t = float(fr["pts_time"])
            if t - pts[-1] >= min_len:
                pts.append(t)
    except Exception:
        pass  # 拿不到就只当"没检出切换"，不编数字
    return pts


def frame_luma(path: str, ts: float) -> float | None:
    """抽单帧的平均亮度（0-255）。用 signalstats 的 YAVG。

    ⚠️ 踩过的坑（ffmpeg 6.1 / Lavf62）：
    `signalstats,metadata=print:file=-` 在这个版本下**什么都不输出**（静默失败），
    而 `signalstats,metadata=print` 把 `lavfi.signalstats.YAVG=…` 打到 **stderr**。
    所以：filter 只写 `metadata=print`，输出只搜 stderr。两处都别改，改一处就静默失效。
    """
    r = _run([
        "ffmpeg", "-hide_banner", "-nostats",
        "-ss", f"{ts:.2f}", "-i", path, "-frames:v", "1",
        "-vf", "signalstats,metadata=print",
        "-f", "null", "-",
    ], timeout=60)
    # 取第一个 YAVG = 目标时间点那一帧
    m = re.search(r"lavfi\.signalstats\.YAVG=([\d.]+)", r.stderr or "")
    return float(m.group(1)) if m else None


# ── 单片检查 ───────────────────────────────────────────────────────
def check_one(path: str) -> dict[str, Any]:
    res: dict[str, Any] = {
        "file": Path(path).name, "path": str(Path(path).resolve()),
        "issues": [], "facts": {},
    }

    def add(level: str, code: str, msg: str):
        res["issues"].append({"level": level, "code": code, "msg": msg})

    try:
        info = probe(path)
    except Exception as e:
        add("FAIL", "unreadable", f"读不了这个文件：{e}")
        res["verdict"] = "FAIL"
        return res

    fmt = info.get("format", {})
    vstreams = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    astreams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]

    if not vstreams:
        add("FAIL", "no_video", "没有视频流")
        res["verdict"] = "FAIL"
        return res

    v = vstreams[0]
    dur = float(fmt.get("duration") or v.get("duration") or 0)
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    facts = {
        "duration_s": round(dur, 2),
        "width": w, "height": h,
        "aspect": _aspect_label(w, h),
        "size_mb": round(int(fmt.get("size") or 0) / 1048576, 2),
        "video_codec": v.get("codec_name"),
        "pix_fmt": v.get("pix_fmt"),
        "has_audio": bool(astreams),
    }

    # 1 画幅
    if h and w:
        if h > w:
            add("WARN", "vertical", f"竖片（{w}×{h}）。B站/YouTube 横片更主流，竖片另开一份更稳")
        if w % 2 or h % 2:
            add("FAIL", "odd_size", f"宽高里有奇数（{w}×{h}），部分播放器解不出来")
        if max(w, h) < 720:
            add("WARN", "low_res", f"最长边只有 {max(w, h)}，1080P 平台会提示画质低")

    # 2 时长
    if dur < MIN_DURATION:
        add("FAIL", "too_short", f"只有 {dur:.1f}s，短于 {MIN_DURATION}s")
    elif dur > MAX_DURATION:
        add("WARN", "too_long", f"{dur:.0f}s 超过 {MAX_DURATION:.0f}s，单条发布偏长")

    # 3 音轨
    if not astreams:
        add("FAIL", "no_audio", "没有音频流。无声片在信息流里几乎活不过 2 秒")
        facts["levels"] = []
    else:
        a = astreams[0]
        facts["audio"] = {
            "codec": a.get("codec_name"),
            "sample_rate": a.get("sample_rate"),
            "channels": a.get("channels"),
        }
        lv = audio_levels(path, dur)
        facts["levels"] = lv
        means = [x["mean_db"] for x in lv if x["mean_db"] is not None]
        maxes = [x["max_db"] for x in lv if x["max_db"] is not None]
        facts["mean_db_avg"] = round(sum(means) / len(means), 1) if means else None
        if not means:
            add("WARN", "level_unknown", "量不到音量（可能音轨是空的）")
        else:
            facts["mean_db_avg"] = round(sum(means) / len(means), 1)
            if facts["mean_db_avg"] < QUIET_MEAN_DB:
                add("FAIL", "too_quiet",
                    f"平均音量 {facts['mean_db_avg']}dB（< {QUIET_MEAN_DB}）—— 基本听不到声音")
            elif facts["mean_db_avg"] > LOUD_MEAN_DB:
                add("WARN", "hot", f"平均音量 {facts['mean_db_avg']}dB 偏高（> {LOUD_MEAN_DB}），有压限痕迹")
            if maxes and max(maxes) >= abs(CLIP_MAX_DB):
                add("WARN", "clipping", f"峰值 {max(maxes)}dB 已触顶，会有削波失真")

    # 5 镜头密度
    try:
        pts = shot_boundaries(path)
        shots = []
        for i in range(len(pts) - 1):
            shots.append(round(pts[i + 1] - pts[i], 3))
        if dur > 0:
            tail = round(dur - pts[-1], 3)
            if tail > 0.3:
                shots.append(tail)
        if shots:
            facts["shot_count"] = len(shots)
            facts["avg_shot_s"] = round(sum(shots) / len(shots), 2)
            facts["shots_per_min"] = round(len(shots) / dur * 60, 1)
            facts["shortest_shot_s"] = round(min(shots), 2)
            facts["longest_shot_s"] = round(max(shots), 2)
            if facts["avg_shot_s"] > MAX_AVG_SHOT_S:
                add("WARN", "slow_cut", f"平均镜头 {facts['avg_shot_s']}s 偏长（> {MAX_AVG_SHOT_S}s）")
            if facts["shots_per_min"] > MAX_SHOTS_PER_MIN:
                add("WARN", "fast_cut", f"每分钟 {facts['shots_per_min']} 个镜头，高频硬切")
    except Exception as e:
        add("WARN", "scene_fail", f"镜头切分失败（{type(e).__name__}），这条没量到")

    # 6 首尾黑
    if dur > 1.0:
        try:
            head = frame_luma(path, 0.15)
            tail = frame_luma(path, max(dur - 0.15, 0.0))
            facts["head_luma"] = head
            facts["tail_luma"] = tail
            if head is not None and head < BLACK_LUMA:
                add("WARN", "black_head", f"片头 0.15s 是近黑帧（亮度 {head}），观众第一眼是黑屏")
            if tail is not None and tail < BLACK_LUMA:
                add("WARN", "black_tail", f"片尾是近黑帧（亮度 {tail}），会显得没剪完")
        except Exception:
            add("WARN", "luma_fail", "首尾亮度量不到")

    # 7 帧率
    r_rate = _frac_to_float(v.get("r_frame_rate"))
    a_rate = _frac_to_float(v.get("avg_frame_rate"))
    facts["frame_rate"] = r_rate
    if r_rate and a_rate and abs(r_rate - a_rate) > 0.5:
        add("WARN", "vfr", f"帧率不稳（r={r_rate} vs avg={a_rate}），可能是可变帧率")
    if r_rate and r_rate < 20:
        add("WARN", "low_fps", f"帧率只有 {r_rate}fps，看起来会比 24fps 更'黏'")

    # 8 文件
    if facts["size_mb"] > 500:
        add("WARN", "heavy", f"{facts['size_mb']}MB 偏大，上传和加载都慢")
    if facts["size_mb"] < 0.3 and dur > 5:
        add("WARN", "tiny_file", f"{facts['size_mb']}MB / {dur:.0f}s，码率可能压得太狠")

    res["facts"] = facts
    res["verdict"] = "FAIL" if any(i["level"] == "FAIL" for i in res["issues"]) else (
        "WARN" if res["issues"] else "PASS")
    return res


def _aspect_label(w: int, h: int) -> str:
    """把宽高比归一化成人看的名字。1280:720 和 1920:1080 都要显示成 16:9。"""
    if not w or not h:
        return "?"
    g = math_gcd(w, h)
    key = (w // g, h // g)
    named = {(16, 9): "16:9 横", (9, 16): "9:16 竖", (4, 3): "4:3", (3, 4): "3:4",
             (1, 1): "1:1 方", (4, 5): "4:5", (2, 3): "2:3"}
    if key in named:
        return named[key]
    return f"{key[0]}:{key[1]}"


def math_gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a or 1


# ── 系列一致性（这一项只有跨文件比较才有意义）────────────────────────
def check_series(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """同一个系列（同一目录）里，画幅/编码必须一致。不一致 = 直接报。"""
    out: list[dict[str, Any]] = []
    ok = [r for r in results if r.get("facts", {}).get("width")]
    aspects = {r["facts"]["aspect"] for r in ok}
    if len(aspects) > 1:
        detail = "／".join(f"{r['file']}＝{r['facts']['aspect']}" for r in ok)
        out.append({
            "level": "FAIL",
            "code": "series_aspect_mismatch",
            "msg": f"同系列画幅不一致（{len(aspects)} 种）：{detail}",
        })
    fr = {r["facts"].get("frame_rate") for r in ok if r["facts"].get("frame_rate")}
    if len(fr) > 1:
        out.append({
            "level": "WARN", "code": "series_fps_mismatch",
            "msg": "同系列帧率不一致：" + "／".join(
                f"{r['file']}＝{r['facts']['frame_rate']}" for r in ok if r["facts"].get("frame_rate")),
        })
    cod = {r["facts"].get("video_codec") for r in ok if r["facts"].get("video_codec")}
    if len(cod) > 1:
        out.append({
            "level": "WARN", "code": "series_codec_mismatch",
            "msg": f"同系列编码不一致：{sorted(c for c in cod if c)}",
        })
    if len(ok) >= 2:
        durs = [r["facts"]["duration_s"] for r in ok]
        spread = max(durs) / max(min(durs), 0.1)
        if spread > 4:
            out.append({
                "level": "WARN", "code": "series_len_spread",
                "msg": f"同系列时长差 {spread:.1f} 倍（{min(durs):.1f}s ~ {max(durs):.1f}s）",
            })
    return out


def selfcheck(results: list[dict[str, Any]], *, negative: bool = False) -> list[str]:
    """
    🚨 指标活着吗 —— 按纪律：没有输出的指标和量错的指标长得一模一样。
    对每个「量出来的数值」，看它在样本间有没有变化。
    全一样 = 这一项没在工作（要么静默失败，要么退化成常数）。

    ⚠️ 已知局限（实测踩过）：同一个文件派生出来的多个副本（N1 去音轨 / N2 截短
    都是从同一个 in.mp4 复制的）会让多个指标**合法地**同值 → 误报。
    所以先按文件哈希去重，只在**互不相关的源文件**之间比较。
    """
    warns: list[str] = []
    if len(results) < 2:
        return warns

    # 🚨 负样本**不做**区分度自检（2026-10-05 实测踩过三次才对清楚）。
    # 原因：负样本是**从同一个源文件派生**的（去音轨/ 截短 / 降音量），
    # 画面完全相同 → 亮度等画面指标**必然**同值。自检会永远误报，
    # 而一个永远误报的检查等于没有检查。
    # 区分度的正确验证对象 = **正样本**（真实的不同片子）。
    if negative:
        return warns

    import hashlib
    seen: dict[str, dict] = {}
    for r in results:
        try:
            h = hashlib.sha1(Path(r["path"]).read_bytes()).hexdigest()
        except Exception:
            h = r["path"]
        seen.setdefault(h, r)
    uniq = list(seen.values())
    if len(uniq) < 2:
        return warns

    probes = [
        ("平均音量",lambda f: f.get("mean_db_avg")),
        ("片头亮度", lambda f: f.get("head_luma")),
        ("片尾亮度", lambda f: f.get("tail_luma")),
        ("平均镜头时长", lambda f: f.get("avg_shot_s")),
        ("每分钟镜头数", lambda f: f.get("shots_per_min")),
        ("时长", lambda f: f.get("duration_s")),
    ]
    for name, get in probes:
        vals = [get(r.get("facts", {})) for r in uniq]
        got = [v for v in vals if v is not None]
        if len(got) < 2:
            warns.append(f"⚠️「{name}」只有 {len(got)}/{len(vals)} 个样本量到值 —— 可能静默失败")
            continue
        if max(got) - min(got) < 1e-9:
            warns.append(f"🚨「{name}」{len(uniq)} 个独立样本全是 {got[0]} —— 这一项没在工作")
    return warns


# ── HTML 报告 ──────────────────────────────────────────────────────
CSS = """
*{box-sizing:border-box}
/* 视觉真源 = 库根 DESIGN.md 的角色色（plush / lantern）。不手改颜色。 */
body{margin:0;background:#FBF6EC;color:#332F2A;
 font:15px/1.65 "Avenir Next","Hiragino Sans GB","Helvetica Neue",sans-serif;
 padding:32px 24px}
h1{font-size:22px;margin:0 0 4px;letter-spacing:-.2px}
.sub{color:#555555;font-size:13.5px;margin-bottom:24px}
.card{background:#F8F1E5;border:1px solid #A39678;border-radius:2px;
 padding:18px 20px;margin-bottom:14px}
.card.PASS{border-left:4px solid #555555}
.card.WARN{border-left:4px solid #E0A93F}
.card.FAIL{border-left:4px solid #C8392B}
.fn{font-weight:700;font-size:15.5px;margin-bottom:4px;
 font-family:"Avenir Next",sans-serif}
.meta{color:#555555;font-size:13.5px;margin-bottom:10px}
table.f{border-collapse:collapse;font-size:13px;margin-top:10px;width:100%}
table.f td,table.f th{border:1px solid #A39678;padding:5px 9px;text-align:left}
table.f th{background:#FBF6EC;font-weight:600}
.tag{display:inline-block;font-size:13px;padding:1px 7px;border-radius:2px;
 margin-right:6px;font-weight:700;letter-spacing:.3px}
.tag.FAIL{background:#C8392B;color:#FBF6EC}
.tag.WARN{background:#E0A93F;color:#332F2A}
ul.i{margin:8px 0 0;padding-left:18px}
ul.i li{margin:4px 0;font-size:13.5px}
.note{background:#FBF6EC;border:1px solid #A39678;border-radius:2px;
 padding:16px 20px;font-size:13.5px;color:#332F2A;margin-top:22px}
.note b{color:#C8392B}
code{font-size:13px}
"""
# 元信息不拼成一串（design_codex T2 指纹：形如 A / B / C 的中点串）
SEP = '<span style="color:#A39678">／</span>'


def meta_line(items: list[str]) -> str:
    """多项事实用 ／ 分隔成独立单元 —— 不让它们看起来像一句 AI 摘要。"""
    return SEP.join(x for x in items if x)


def render_html(results: list[dict], series_issues: list[dict], out: Path,
                alive: list[str] | None = None) -> None:
    tally = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for r in results:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1

    parts = [
        "<!doctype html><html lang=zh><meta charset=utf-8>",
        "<title>成片体检报告</title>",
        f"<style>{CSS}</style><body>",
        "<h1>成片体检报告</h1>",
        f'<div class=sub>共 {len(results)} 个文件　'
        f'<b>FAIL {tally["FAIL"]}</b>　'
        f'<b>WARN {tally["WARN"]}</b>　'
        f'PASS {tally["PASS"]}　'
        f'工具 <code>ep-qa.py</code></div>',
    ]
    if alive:
        parts.append('<div class="card WARN"><div class=fn>指标自检</div><ul class=i>')
        for a in alive:
            parts.append(f"<li>{a}</li>")
        parts.append("</ul></div>")
    if series_issues:
        parts.append('<div class="card FAIL"><div class=fn>系列一致性</div><ul class=i>')
        for i in series_issues:
            parts.append(f'<li><span class="tag {i["level"]}">{i["level"]}</span>{i["msg"]}</li>')
        parts.append("</ul></div>")

    for r in results:
        f = r.get("facts", {})
        parts.append(f'<div class="card {r["verdict"]}">')
        parts.append(f'<div class=fn>{r["file"]}</div>')
        parts.append('<div class=meta>' + meta_line([
            f.get("aspect") or "", f'{f.get("width")}×{f.get("height")}' if f.get("width") else "",
            f'{f.get("duration_s")}s' if f.get("duration_s") else "",
            f'{f.get("size_mb")}MB' if f.get("size_mb") else "",
            f.get("video_codec") or "", f.get("pix_fmt") or "",
            f'{f.get("frame_rate")}fps' if f.get("frame_rate") else "",
        ]) + "</div>")
        extra = []
        if f.get("shot_count"):
            extra.append(f'镜头 {f["shot_count"]} 个')
            extra.append(f'平均 {f["avg_shot_s"]}s')
            extra.append(f'每分钟 {f["shots_per_min"]} 刀')
            extra.append(f'最短 {f["shortest_shot_s"]}s')
        if f.get("mean_db_avg") is not None:
            extra.append(f'平均音量 {f["mean_db_avg"]}dB')
        if f.get("head_luma") is not None:
            extra.append(f'片头亮度 {f["head_luma"]}')
            extra.append(f'片尾亮度 {f.get("tail_luma")}')
        if extra:
            parts.append('<div class=meta>' + meta_line(extra) + "</div>")
        if r["issues"]:
            parts.append('<ul class=i>')
            for i in r["issues"]:
                parts.append(f'<li><span class="tag {i["level"]}">{i["level"]}</span>{i["msg"]}</li>')
            parts.append("</ul>")
        parts.append("</div>")

    parts.append(
        '<div class=note><b>⛔ 这份报告不判审美。</b>'
        '节奏快慢、构图、颜色、角色像不像 —— 全部归 Seth。<br>'
        '这里只报<b>可测量的交付事实</b>：能不能播、会不会黑屏、系列齐不齐。<br>'
        '出处：做法借鉴 OpenMontage（github.com/calesthio/OpenMontage，'
        'calesthio，GNU AGPLv3）的 <code>visual_qa</code>。'
        '本工具代码为独立实现，未复制其源码。</div>'
    )
    parts.append("</body></html>")
    out.write_text("".join(parts), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--series-dir", default=None, help="整个目录当成一个系列检查")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--html", dest="html_out")
    ap.add_argument("--negative", action="store_true",
                    help="这批是故意做坏的负样本 → 不跑区分度自检")
    a = ap.parse_args()

    files = list(a.files)
    if a.series_dir:
        for ext in ("*.mp4", "*.mov", "*.m4v"):
            files += [str(p) for p in sorted(Path(a.series_dir).glob(ext))]
    files = [f for f in dict.fromkeys(files) if Path(f).exists()]
    if not files:
        print("没有可检查的文件", file=sys.stderr)
        return 2

    results = [check_one(f) for f in files]
    series = check_series(results) if len(results) > 1 else []
    alive = selfcheck(results, negative=a.negative)

    if a.json_out:
        Path(a.json_out).write_text(
            json.dumps({"results": results, "series_issues": series,
                        "selfcheck": alive},
                       ensure_ascii=False, indent=2), encoding="utf-8")
    if a.html_out:
        render_html(results, series, Path(a.html_out), alive)

    for r in results:
        print(f'[{r["verdict"]}] {r["file"]}')
        for i in r["issues"]:
            print(f'    {i["level"]}  {i["msg"]}')
    for i in series:
        print(f'[系列] {i["level"]}  {i["msg"]}')
    for w in alive:
        print(f'[自检] {w}')

    if any(i["level"] == "FAIL" for i in series):
        return 2
    if any(r["verdict"] == "FAIL" for r in results):
        return 2
    if any(r["verdict"] == "WARN" for r in results) or series:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())