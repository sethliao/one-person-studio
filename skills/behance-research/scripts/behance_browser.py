#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Behance 取数层（只读）· 浏览器补充模块
=========================================
处理 **服务端不渲染** 的两类列表：
  - /<user>/following     关注列表（客户端渲染 + 模态框懒加载）
  - /<user>/moodboards    moodboard 索引（链接本身是 SSR 的）

依赖宿主机的 `agent-browser`。公开内容，无需登录。

用法
----
    P=~/.workbuddy/binaries/python/versions/3.13.12/bin/python3
    $P behance_browser.py following  seth_liao -o following.json
    $P behance_browser.py moodboards seth_liao -o moodboard-index.json

⚠️ 两个已踩过的坑（脚本内已处理，自行调用 agent-browser 时要记得）：
  1. headless Chromium 默认 UA 会被 Behance 判爬虫 → 所有 URL 一律 HTTP 400。
     必须 `--headers '{"User-Agent": "<真 Chrome UA>"}'`。
  2. 关注列表的模态框是 **内层滚动容器**，window.scrollTo 无效。
     要滚所有 scrollHeight > clientHeight + 80 的 div。
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = json.dumps({"User-Agent": UA})

# Behance 常见 creative field —— 用于把「Motion GraphicsAnimation3D Motion」切开
FIELDS = [
    "Motion Graphics", "3D Motion", "3D Art", "3D Modeling", "Character Design",
    "Art Direction", "Graphic Design", "Illustration", "Animation", "Digital Art",
    "Branding", "Advertising", "UI/UX", "Web Design", "Icon Design", "Photography",
    "Typography", "Packaging", "Logo Design", "Fashion", "Product Design",
    "Industrial Design", "Interior Design", "Sound Design", "Music", "Film",
    "Cinematography", "Concept Art", "Drawing", "Painting", "Sculpting", "Fine Arts",
    "Game Design", "Toy Design", "Creative Direction", "Visualization", "CGI",
    "Styleframing", "Pattern Design", "Landscape Design", "Set Design",
    "Interaction Design", "Editorial Design", "Print Design", "Architecture",
]

ENV = dict(os.environ, PATH=os.environ.get("PATH", "") + ":/opt/homebrew/bin")


def ab(*args, timeout=90):
    """跑一条 agent-browser 命令，返回 stdout。"""
    p = subprocess.run(["agent-browser", *args], capture_output=True, text=True,
                       timeout=timeout, env=ENV)
    return p.stdout.strip()


def ab_eval(js, timeout=90):
    out = ab("eval", js, timeout=timeout)
    # agent-browser eval 会把结果 JSON 序列化后打印
    try:
        return json.loads(out)
    except Exception:
        return out


def open_url(url):
    r = ab("open", url, "--headers", HEADERS)
    if "400" in r or "Bad Request" in r:
        raise SystemExit("打开失败（UA 头没生效？）：" + r[:200])
    return r


SCROLL_JS = (
    "(() => {const ds=[...document.querySelectorAll('div')]"
    ".filter(d=>d.scrollHeight>d.clientHeight+80);"
    "ds.forEach(d=>d.scrollTop+=Math.max(d.clientHeight,700));"
    "const n=[...document.querySelectorAll('*')]"
    ".filter(e=>e.children.length===0&&e.textContent.trim()==='Follow').length;"
    "return n;})()"
)


def scroll_all(max_rounds=70, pause=0.6):
    """滚到底 —— 关注列表的模态框是内层滚动容器，window.scrollTo 无效。

    以「Follow 按钮数量」为增长信号，连续 4 轮不涨就认为到底。
    """
    last, stall = -1, 0
    for _ in range(max_rounds):
        n = ab_eval(SCROLL_JS)
        n = n if isinstance(n, int) else 0
        if n <= last:
            stall += 1
            if stall >= 4:
                break
        else:
            stall = 0
        last = max(last, n)
        time.sleep(pause)
    return last


NUM_RE = re.compile(r"^\d+(?:\.\d+)?[KM]?$")


def split_stats(blob):
    """'8.1K119.3K' → (8100, 119300)；'1005.2K' → (1005, 2000)。

    Behance 把两组数字连排（appreciations 紧接 views，无分隔符），必须切回两个数。
    规则：
      1) 两个片段都得是合法数字（可带 K/M 后缀）；
      2) 优先「第一段以 K/M 结尾」的切法（说明边界就在后缀后）；
      3) 再受约束 appreciations <= views（Behance 上恒成立）；
      4) 仍多解时取第一段最大者。找不到合法切法 → 整串当一个数并标记存疑。
    """
    blob = (blob or "").strip()
    cands = []
    for i in range(1, len(blob)):
        a, b = blob[:i], blob[i:]
        if not NUM_RE.match(a) or not NUM_RE.match(b):
            continue
        ai, bi = to_num(a), to_num(b)
        if ai is None or bi is None:
            continue
        cands.append((a.endswith(("K", "M")), ai <= bi, ai, bi))
    if not cands:
        return to_num(blob), None
    strict = [c for c in cands if c[1]]
    pool = strict or cands
    pool.sort(key=lambda c: (c[0], c[2]), reverse=True)
    return pool[0][2], pool[0][3]


def to_num(s):
    s = (s or "").strip()
    mult = {"K": 1_000, "M": 1_000_000}
    if s and s[-1] in mult:
        return int(float(s[:-1]) * mult[s[-1]])
    try:
        return int(float(s))
    except Exception:
        return None


def split_fields(blob):
    """'Motion GraphicsAnimation3D Motion' → ['Motion Graphics', '3D Motion']"""
    out, rest = [], (blob or "").strip()
    while rest:
        hit = None
        for f in sorted(FIELDS, key=len, reverse=True):
            if rest.startswith(f):
                hit = f
                break
        if not hit:                      # 认不出的尾巴，整段留下
            out.append(rest)
            break
        out.append(hit)
        rest = rest[len(hit):]
    return out


def cmd_following(username):
    url = f"https://www.behance.net/{username}/following"
    print(f"打开 {url}", file=sys.stderr)
    open_url(url)
    time.sleep(2)
    print("滚动模态框懒加载…", file=sys.stderr)
    scroll_all()
    text = ab_eval("document.body.innerText") or ""
    if not isinstance(text, str):
        text = json.dumps(text)
    text = text.replace("\\n", "\n").strip('"')

    # 卡片刻在 "\nFollow\n" 之间：段 = 上一张的统计 + 本张的 名字/地点/领域
    # 先砍掉页头（"FollowersFollowingMoodboards Following\n"），取最后一个 "Following\n" 之后
    body = re.split(r"Following\n", text)[-1]
    parts = body.split("\nFollow\n")
    cards = []
    for i, part in enumerate(parts):
        lines = [l for l in part.split("\n") if l.strip() != ""]
        if not lines:
            continue
        if i == 0:
            stats = None
            rest = lines
        else:
            stats = lines[0]
            rest = lines[1:]
            if rest and rest[0] == "PRO":
                rest = rest[1:]
            if cards:
                a, v = split_stats(stats)
                cards[-1]["appreciations"], cards[-1]["views"] = a, v
        if len(rest) >= 1:
            name = rest[0]
            loc = rest[1] if len(rest) > 1 else None
            fld = rest[2] if len(rest) > 2 else ""
            cards.append({"name": name, "location": loc,
                          "fields": split_fields(fld),
                          "appreciations": None, "views": None,
                          "username": None})
    bad = sum(1 for c in cards if (c["appreciations"] or 0) > (c["views"] or 0) or c["views"] is None)
    print(f"解析出 {len(cards)} 张卡片（{bad} 张统计存疑，标记为 views=null）", file=sys.stderr)
    return cards


def cmd_moodboards(username):
    url = f"https://www.behance.net/{username}/moodboards"
    print(f"打开 {url}", file=sys.stderr)
    open_url(url)
    time.sleep(2)
    js = ("JSON.stringify([...document.querySelectorAll('a[href*=\"/moodboard/\"]')]"
          ".map(a=>a.getAttribute('href'))"
          ".filter((v,i,s)=>v&&s.indexOf(v)===i))")
    hrefs = ab_eval(js)
    if isinstance(hrefs, str):
        hrefs = json.loads(hrefs)
    out = []
    for h in hrefs or []:
        m = re.match(r"/moodboard/(\d+)/(.*)$", h or "")
        if m:
            out.append({"id": int(m.group(1)), "slug": m.group(2), "href": h})
    print(f"解析出 {len(out)} 个 moodboard", file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser(description="Behance 客户端渲染列表取数（需 agent-browser）")
    ap.add_argument("command", choices=["following", "moodboards"])
    ap.add_argument("username")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()

    data = (cmd_following if a.command == "following" else cmd_moodboards)(a.username)
    js = json.dumps(data, ensure_ascii=False, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
        print(f"→ {a.out}", file=sys.stderr)
    else:
        print(js)


if __name__ == "__main__":
    main()
