#!/usr/bin/env python3
"""统一收藏抓取入口 —— 并发 + 缓存 + 断点。

「很慢」的根因：原来每个平台串行调用 opencli，每次都要起一轮浏览器交互（3–10s），
9 个平台累加起来就是几分钟。这里做三件事：

  1. **并发**：所有平台同时跑（subprocess 是 IO 密集，线程池足够）
  2. **缓存**：输出文件够新（默认 6h）就直接跳过 —— 重跑近乎瞬时
  3. **容错**：单个平台失败不影响其它；失败的单独列出，可 --only 重试

用法：
  python3 collect_all.py                    # 并发抓全部（命中缓存则跳过）
  python3 collect_all.py --force            # 忽略缓存，全量重抓
  python3 collect_all.py --ttl 0            # 缓存立即过期
  python3 collect_all.py --only bili,xhs    # 只抓指定平台
  python3 collect_all.py --list             # 只看有哪些平台
"""
import json, os, re, subprocess, argparse, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
OPENCLI = "~/.local/bin/opencli"


def find_coll():
    for c in [os.path.join(HERE, "data", "collect"),
              os.path.join(HERE, "..", "data", "collect"),
              os.path.join(os.getcwd(), "data", "collect")]:
        if os.path.isdir(c):
            return os.path.abspath(c)
    os.makedirs(os.path.join(HERE, "data", "collect"), exist_ok=True)
    return os.path.abspath(os.path.join(HERE, "data", "collect"))


COLL = find_coll()

# ---------------------------------------------------------------------------
# 任务表：key -> 说明 + opencli 命令 + 输出文件 + 追加参数
# ---------------------------------------------------------------------------
JOBS = {
    "bili":   dict(desc="B站收藏夹",       cmd=["bilibili", "favorite", "--limit", "400", "-f", "json"],
                   out="bili_favorite.json",                              extra=[]),
    "xhs":    dict(desc="小红书收藏",       cmd=["xiaohongshu", "saved", "--limit", "100", "-f", "json"],
                   out="xhs_saved.json",        extra=["--site-session", "persistent"]),
    "xhslike":dict(desc="小红书赞过",       cmd=["xiaohongshu", "liked", "--limit", "100", "-f", "json"],
                   out="xhs_liked.json",        extra=["--site-session", "persistent"]),
    "yt":     dict(desc="YouTube 稍后再看", cmd=["youtube", "watch-later", "-f", "json"],
                   out="yt_watchlater.json",                               ),
    "weibo":  dict(desc="微博收藏",         cmd=["weibo", "favorites", "-f", "json"],
                   out="weibo_favorites.json",                             ),
    "zhihu":  dict(desc="知乎收藏夹",       cmd=["zhihu", "collections", "-f", "json"],
                   out="zhihu_collections.json",                           ),
}

# 需要两步 / 特殊后处理的
SPECIAL = {
    "zhihu_items": dict(desc="知乎收藏夹条目", out="zhihu_items.json"),
    "pinterest":   dict(desc="Pinterest Pin",  out="pinterest_pins.json"),
}


def clean(s):
    """剔 opencli 日志噪音。"""
    return re.sub(
        r"[^\n]*(Update available|Run: npm|UNDICI-EHPA|trace-warnings|symlink|Could not create)[^\n]*\n?",
        "", s)


def parse_loose(s):
    """从混杂输出里解析出第一个 JSON 值。

    用 raw_decode：从第一个 `[` 或 `{` 开始解析**一个**值，**自动忽略尾部垃圾**。
    比「找最后一个括号」稳 —— JSON 内部也可能含 `[`/`]`（那是上一版踩的坑）。
    """
    s = clean(s)
    cands = sorted([i for i in (s.find("["), s.find("{")) if i >= 0])
    if not cands:
        raise ValueError("输出里找不到 JSON 起始符: %s" % s[:120].replace("\n", " "))
    dec = json.JSONDecoder()
    last = None
    for i in cands:
        try:
            obj, _ = dec.raw_decode(s[i:])
            return obj
        except Exception as e:
            last = e
    raise ValueError("raw_decode 失败: %s | %s" % (last, s[:120].replace("\n", " ")))


def run_job(key, cfg, force, ttl):
    outp = os.path.join(COLL, cfg["out"])
    if not force and ttl > 0 and os.path.exists(outp):
        age = (time.time() - os.path.getmtime(outp)) / 3600.0
        if age < ttl:
            try:
                n = len(json.load(open(outp, encoding="utf-8")))
            except Exception:
                n = "?"
            return dict(key=key, ok=True, cached=True, n=n, secs=0.0,
                        msg="缓存命中（%.1fh 前）" % age)

    t0 = time.time()
    args = [OPENCLI] + cfg["cmd"] + cfg.get("extra", [])
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return dict(key=key, ok=False, n=0, secs=time.time() - t0, msg="超时 180s")

    raw = r.stdout
    try:
        data = parse_loose(raw)
    except Exception as e:
        return dict(key=key, ok=False, n=0, secs=time.time() - t0,
                    msg="解析失败 %s" % str(e)[:150])

    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    if not isinstance(data, list):
        return dict(key=key, ok=False, n=0, secs=time.time() - t0, msg="返回不是列表：%s" % type(data).__name__)

    json.dump(data, open(outp, "w"), ensure_ascii=False, indent=1)
    return dict(key=key, ok=True, cached=False, n=len(data), secs=time.time() - t0, msg="")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="忽略缓存全量重抓")
    ap.add_argument("--ttl", type=float, default=6.0, help="缓存有效期（小时），0=不用缓存")
    ap.add_argument("--only", default="", help="只抓这些 key，逗号分隔")
    ap.add_argument("--list", action="store_true", help="列出任务表")
    a = ap.parse_args()

    if a.list:
        print("%-10s %-18s %s" % ("key", "说明", "输出"))
        for k, c in list(JOBS.items()) + list(SPECIAL.items()):
            tag = "  ⚙︎需专用脚本" if k in SPECIAL else ""
            print("%-10s %-18s %s%s" % (k, c["desc"], c["out"], tag))
        return

    todo = list(JOBS.items())
    if a.only:
        want = {x.strip() for x in a.only.split(",") if x.strip()}
        todo = [(k, c) for k, c in todo if k in want]
    if not todo:
        print("没有可跑的任务。用 --list 看 key。")
        return

    print("并发抓取 %d 个平台（缓存 TTL=%.0fh，%s）…\n" % (len(todo), a.ttl, "忽略缓存" if a.force else "命中即跳过"))
    t0 = time.time()
    results = []
    # 并发：8 线程足够（opencli 是浏览器桥，别开太多把 Chrome 挤爆）
    with ThreadPoolExecutor(max_workers=min(6, len(todo))) as ex:
        futs = {ex.submit(run_job, k, c, a.force, a.ttl): (k, c) for k, c in todo}
        for f in as_completed(futs):
            k, c = futs[f]
            try:
                res = f.result()
            except Exception as e:
                res = dict(key=k, ok=False, n=0, secs=0, msg=str(e))
            res["desc"] = c["desc"]
            results.append(res)
            flag = "✅" if res["ok"] else "❌"
            tail = ("缓存 %s 条" % res["n"]) if res.get("cached") else ("%s 条 / %.1fs" % (res["n"], res["secs"]))
            print("  %s %-9s %-18s %s %s" % (flag, k, c["desc"], tail, res["msg"]))
    el = time.time() - t0

    okn = sum(1 for r in results if r["ok"])
    total = sum(r["n"] for r in results if isinstance(r["n"], int))
    print("\n完成：%d/%d 平台成功，共 %d 条，耗时 %.1fs" % (okn, len(results), total, el))
    bad = [r for r in results if not r["ok"]]
    if bad:
        print("\n失败（可单独重试：--only %s）:" % ",".join(r["key"] for r in bad))
        for r in bad:
            print("  · %s %s — %s" % (r["key"], r["desc"], r["msg"]))
    print("\n下一步：python3 analyze_collections.py && python3 build_collections_board.py")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
