#!/usr/bin/env python3
"""小红书封面回填（v2 · 走原生 download 命令 + 并发）。

为什么是这个方案 —— 已穷尽的排查（2026-09-24）：
  ✗ `saved` / `liked` / `feed` / `note` 的返回列固定，**没有任何封面字段**，也无 flag 可加
  ✗ 内部 feed API 被 `x-s` 签名拦死（HTTP 406 code -1）
  ✗ 同源 fetch 笔记页 HTML：只在 38% 的笔记里含图床地址，且逐条很慢
  ✓ `xiaohongshu download` 是**原生适配器**，一条笔记 14 张图 9 秒下完

所以：并发跑 download → **只取第 1 张（封面）** → 存进看板同级的 `covers/` → 删掉临时下载。
看板引用相对路径，不依赖网络、不依赖登录态。

用法： python3 fetch_covers.py [--workers 4] [--limit N] [--keep]
输出： covers/<note_id>.jpg  +  data/collect/xhs_covers_local.json
"""
import json, os, re, shutil, subprocess, argparse, sys, tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
OPENCLI = "~/.local/bin/opencli"
PROFILE = "hegpkpwu"          # 主号（小红书已登录）


def find_coll():
    for c in [os.path.join(HERE, "data", "collect"),
              os.path.join(HERE, "..", "data", "collect"),
              os.path.join(os.getcwd(), "data", "collect")]:
        if os.path.isdir(c):
            return os.path.abspath(c)
    return os.path.abspath(os.path.join(HERE, "data", "collect"))


def find_cover_dir():
    """封面存到看板同级 —— 看板若在 vault 的 collections-ledger/，封面也放那儿。"""
    for c in [os.path.join(HERE, "covers"),
              os.path.join(HERE, "..", "collections-ledger", "covers"),
              os.path.join(os.getcwd(), "covers")]:
        if os.path.isdir(os.path.dirname(c)):
            return os.path.abspath(c)
    return os.path.abspath(os.path.join(HERE, "covers"))


COLL = find_coll()
COVERS = find_cover_dir()


def note_urls():
    """从已抓的收藏/赞过数据里取出 (note_id, 完整签名 URL)。"""
    out = {}
    for fn in ("xhs_saved.json", "xhs_liked.json"):
        p = os.path.join(COLL, fn)
        if not os.path.exists(p):
            continue
        for x in json.load(open(p, encoding="utf-8")):
            u = x.get("url", "")
            ids = re.findall(r"[0-9a-f]{24}", u)
            tok = re.search(r"xsec_token=([^&]+)", u)
            if not ids or not tok:
                continue
            nid = ids[-1]                          # 最后一个 24hex 才是笔记 id
            if nid in out:
                continue
            out[nid] = ("https://www.xiaohongshu.com/explore/%s?xsec_token=%s&xsec_source=pc_user"
                        % (nid, tok.group(1)))
    return out


def one(nid, url, keep):
    """下一条笔记 → 取第 1 张图当封面 → 清掉其余。"""
    dst = os.path.join(COVERS, nid + ".jpg")
    if os.path.exists(dst) and os.path.getsize(dst) > 1024:
        return dict(nid=nid, ok=True, cached=True)

    tmp = tempfile.mkdtemp(prefix="xhsdl_")
    try:
        args = [OPENCLI, "--profile", PROFILE, "xiaohongshu", "download", url,
                "--output", tmp, "-f", "json", "--site-session", "persistent"]
        subprocess.run(args, capture_output=True, text=True, timeout=180)
        d = os.path.join(tmp, nid)
        if not os.path.isdir(d):
            return dict(nid=nid, ok=False, msg="没下到目录")
        # 文件名形如 <note_id>_1.jpg，1 就是封面
        cands = [f for f in os.listdir(d)
                 if re.match(r"^%s_\d+\." % re.escape(nid), f)
                 and f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
        if not cands:
            return dict(nid=nid, ok=False, msg="目录里没有图片")
        cands.sort(key=lambda f: int(re.search(r"_(\d+)\.", f).group(1)))
        os.makedirs(COVERS, exist_ok=True)
        shutil.copyfile(os.path.join(d, cands[0]), dst)
        return dict(nid=nid, ok=True, cover="covers/%s.jpg" % nid, n=len(cands))
    except subprocess.TimeoutExpired:
        return dict(nid=nid, ok=False, msg="超时")
    except Exception as e:
        return dict(nid=nid, ok=False, msg=str(e)[:80])
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--keep", action="store_true", help="保留下载的原始文件（默认删掉）")
    a = ap.parse_args()

    jobs = note_urls()
    if a.limit:
        jobs = dict(list(jobs.items())[: a.limit])
    print("目标 %d 条笔记 → 封面目录 %s" % (len(jobs), COVERS))
    if not jobs:
        return 1

    os.makedirs(COVERS, exist_ok=True)
    res, done = [], 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(one, nid, url, a.keep): nid for nid, url in jobs.items()}
        for f in as_completed(futs):
            try:
                r = f.result()
            except Exception as e:
                r = dict(nid=futs[f], ok=False, msg=str(e)[:80])
            res.append(r)
            done += 1
            if done % 5 == 0 or done == len(jobs):
                print("  …%d/%d，成功 %d" % (done, len(jobs), sum(1 for x in res if x["ok"])))

    ok = [r for r in res if r["ok"]]
    mapping = {r["nid"]: r.get("cover", "covers/%s.jpg" % r["nid"]) for r in ok}
    json.dump(mapping, open(os.path.join(COLL, "xhs_covers_local.json"), "w"),
              ensure_ascii=False, indent=1)

    print("\n成功 %d / %d (%.0f%%)" % (len(ok), len(res), 100.0 * len(ok) / max(len(res), 1)))
    bad = [r for r in res if not r["ok"]]
    if bad:
        from collections import Counter
        print("失败原因:", Counter(r.get("msg", "?") for r in bad).most_common(5))
    fs = os.listdir(COVERS)
    if fs:
        print("→ covers/ 共 %d 张，%.1f MB" % (len(fs),
              sum(os.path.getsize(os.path.join(COVERS, f)) for f in fs) / 1e6))
    print("→ data/collect/xhs_covers_local.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
