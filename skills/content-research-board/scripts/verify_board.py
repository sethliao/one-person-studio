#!/usr/bin/env python3
"""交付前校验：看板里的**每一条链接**与**每一张本地图**都必须是真的。

为什么必须有它 —— 这条铁律已经踩过两次：
  ① 手写 HTML 时**编造**了 5 个封面 URL；
  ② Markdown 笔记里凭印象敲了一个假的 YouTube video id（写 `JmE1kVbA_-k`，真实 `_rRPcAll56F8`）。
  两次的共同点：**产物看起来像人写的，所以"看起来没问题"**。
  所以机器校验不是可选项。

校验三件事：
  A. 看板内嵌 JSON 的条数 == analysis.json 条数（防止建板时静默丢数据）
  B. 看板里每个 url 都出现在源数据里（防止编造 / 拼接错误）
  C. 每个 `covers/xxx.jpg` 相对引用都有真实文件，且体积 > 1 KB（防止 0 字节/占位图）

用法：
  python3 verify_board.py                          # 校验默认两份看板
  python3 verify_board.py --board <html> [--board <html> ...]
退出码：0 = 全部通过；1 = 有 ❌
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_BOARDS = [
    os.path.join(HERE, "collections-board.html"),
    "~/Documents/hermes_vault_clean/003-Workbench/collections-ledger/collections-board.html",
]
SRC = os.path.join(HERE, "data", "collect", "analysis.json")


def find_embedded_json(html):
    """把看板里 <script id="DATA"> 那段 JSON 抠出来。

    看板用的是 `<script type="application/json" id="DATA">` + `JSON.parse(el.textContent)`，
    —— 比 `var DATA = {...}` 稳（不怕内容里出现 `;` 或 `</script>` 之外的干扰）。
    """
    m = re.search(r'<script[^>]*\bid=["\']DATA["\'][^>]*>(.*?)</script>', html, re.S)
    if m:
        return m.group(1).strip()
    # 兜底：老写法
    m = re.search(r"var\s+DATA\s*=\s*(\{.*?\});\s*\n", html, re.S)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", action="append", default=[])
    ap.add_argument("--src", default=SRC)
    a = ap.parse_args()
    boards = a.board or DEFAULT_BOARDS

    src = json.load(open(a.src, encoding="utf-8"))
    pub = [i for i in src["items"] if not i["private"]]
    src_urls = {i["url"] for i in pub if i["url"]}
    print("源数据：%s" % a.src)
    print("  共 %d 条 / 公开 %d 条 / 不重复 url %d 个\n" % (
        len(src["items"]), len(pub), len(src_urls)))

    bad_total = 0
    for bp in boards:
        print("=" * 68)
        if not os.path.exists(bp):
            print("❌ %s —— 文件不存在" % bp)
            bad_total += 1
            continue
        html = open(bp, encoding="utf-8").read()
        blob = find_embedded_json(html)
        problems = []

        # A. 条数
        if not blob:
            problems.append("找不到内嵌 DATA JSON（建板脚本的变量名改了？）")
            n_items, urls, thumbs = 0, set(), []
        else:
            data = json.loads(blob)
            items = data.get("items", [])
            n_items = len(items)
            urls = {i.get("u", "") for i in items if i.get("u")}
            thumbs = [(i.get("th") or "") for i in items]
            print("看板：%s  (%.0f KB)" % (bp, len(html.encode()) / 1024))
            print("  内嵌 %d 条 / 源公开 %d 条" % (n_items, len(pub)))
            if n_items != len(pub):
                problems.append("条数不符：看板 %d ≠ 源 %d" % (n_items, len(pub)))
            else:
                print("  ✅ A. 条数一致")

        # B. 链接必须来自源数据
        if urls:
            ghost = sorted(urls - src_urls)
            print("  链接 %d 个，其中不在源数据里的 %d 个" % (len(urls), len(ghost)))
            if ghost:
                problems.append("发现 %d 个源数据里没有的链接（疑似编造）" % len(ghost))
                for g in ghost[:5]:
                    print("     ❌ %s" % g[:110])
            else:
                print("  ✅ B. 无编造链接")

        # C. 本地封面必须存在且非空
        local = sorted({t for t in thumbs if t.startswith("covers/")})
        if local:
            bdir = os.path.dirname(os.path.abspath(bp))
            miss = [t for t in local
                    if not os.path.exists(os.path.join(bdir, t))
                    or os.path.getsize(os.path.join(bdir, t)) < 1024]
            print("  本地封面引用 %d 个，缺失/过小 %d 个" % (len(local), len(miss)))
            if miss:
                problems.append("%d 张本地封面不存在或 < 1 KB" % len(miss))
                for m in miss[:5]:
                    print("     ❌ %s" % m)
            else:
                print("  ✅ C. 本地封面全部就位（同目录 covers/）")
        else:
            print("  · 无本地封面引用（可跳过 C）")

        print()
        if problems:
            print("  ❌ 未通过：")
            for p in problems:
                print("     · %s" % p)
            bad_total += len(problems)
        else:
            print("  ✅ 全部通过")

    print("\n" + "=" * 68)
    if bad_total:
        print("结果：❌ %d 项问题 —— **不要交付**，先修。" % bad_total)
        return 1
    print("结果：✅ 0 个 ❌ —— 可以交付。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
