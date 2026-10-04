#!/usr/bin/env python3
"""一键发布：抓取 → 封面 → 分析 → 建板 → 同步进 vault。

为什么要有它 —— 之前这条链是**手动的五步**，而且最后一步「把数据 cp 进 vault」是
隐形的（不在任何脚本里），漏掉就会出现「workspace 的 analysis.json 是新的、
vault 里的看板读的却是旧数据」这种对不上的状态。

所以：把五个步骤 + 两条同步路径都收进一个入口，**每步都打印它到底动了哪个文件**。

链路：
  1. collect_all.py          并发抓 6 平台收藏 → data/collect/*.json（带 TTL 缓存）
  2. fetch_covers.py         小红书封面（原生 download 命令 + 并发，只留第 1 张）
  3. analyze_collections.py  归一化 + 去重 + 规则式分类 → data/collect/analysis.json
  4. build_collections_board.py
        ├─ 工作区产物  <HERE>/collections-board.html   + <HERE>/covers/
        └─ vault 产物  <VAULT>/003-Workbench/collections-ledger/collections-board.html + covers/
  5. 同步 data/collect/*.json → vault 003-Workbench/data/collect/（**保留 vault 自己的 picked.json**）
  6. verify_board.py         交付前校验：条数一致 / 无编造链接 / 本地封面真实存在（0 个 ❌ 才算完成）

用法：
  python3 publish.py                       # 全量（缓存命中则跳过抓取/封面）
  python3 publish.py --skip-collect        # 只重跑封面 → 分析 → 建板
  python3 publish.py --skip-covers         # 跳过 20 分钟的封面回填
  python3 publish.py --force               # 忽略所有缓存
  python3 publish.py --profile nkc4pnjs --tag _sethn   # 抓另一个 Chrome profile 的账号
  python3 publish.py --dry                 # 只打印路径与将执行的命令，不动手
"""
import argparse, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

VAULT_DEFAULT = "~/Documents/hermes_vault_clean"
ROOT_REL = os.path.join(HERE, "..")           # 若脚本被复制进 vault，这条会指向 vault

# 这些是「生成物」，可以被覆盖
SYNC_FILES = [
    "analysis.json", "bili_favorite.json", "xhs_saved.json", "xhs_liked.json",
    "yt_watchlater.json", "weibo_favorites.json", "zhihu_collections.json",
    "zhihu_items.json", "pinterest_pins.json", "dy_collections.json",
    "xhs_covers_local.json",
]
# vault 自己独有的，**绝不能覆盖**
KEEP_FILES = ["picked.json"]


def sh(cmd, **kw):
    print("  $ " + " ".join(cmd))
    return subprocess.run(cmd, **kw)


def step(n, total, title):
    print("\n" + "=" * 68)
    print("[%d/%d] %s" % (n, total, title))
    print("=" * 68)


def sync_to_vault(coll, vault_data, dry=False):
    """把工作区的采集数据同步进 vault；picked.json 只读不覆盖。"""
    print("  同步 %s" % coll)
    print("    → %s" % vault_data)
    if not dry:
        os.makedirs(vault_data, exist_ok=True)
    n = 0
    for f in SYNC_FILES:
        s = os.path.join(coll, f)
        if not os.path.exists(s):
            continue
        d = os.path.join(vault_data, f)
        if not dry and (not os.path.exists(d) or os.path.getsize(d) != os.path.getsize(s)):
            shutil.copyfile(s, d)
        if not dry:
            n += 1
        print("    · %-26s %7.0f KB%s" % (f, os.path.getsize(s) / 1024,
              "  (新)" if not os.path.exists(d) else ""))
    kept = [k for k in KEEP_FILES if os.path.exists(os.path.join(vault_data, k))]
    if kept:
        print("    ⚠️ 保留 vault 自有文件（不覆盖）：%s" % ", ".join(kept))
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=VAULT_DEFAULT, help="vault 根目录")
    ap.add_argument("--skip-collect", action="store_true")
    ap.add_argument("--skip-covers", action="store_true")
    ap.add_argument("--force", action="store_true", help="忽略抓取/封面缓存")
    ap.add_argument("--ttl", type=float, default=6.0)
    ap.add_argument("--workers", type=int, default=3, help="封面并发（3 足够，再多 bridge 会串行）")
    ap.add_argument("--profile", default="")
    ap.add_argument("--tag", default="")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    coll = os.path.join(HERE, "data", "collect")
    vault_data = os.path.join(a.vault, "003-Workbench", "data", "collect")
    vault_ledger = os.path.join(a.vault, "003-Workbench", "collections-ledger")
    ws_board = os.path.join(HERE, "collections-board.html")
    vault_board = os.path.join(vault_ledger, "collections-board.html")

    print("链路配置")
    print("  工作区脚本目录  %s" % HERE)
    print("  采集数据目录    %s" % coll)
    print("  vault 根        %s" % a.vault)
    print("  vault 数据目录  %s" % vault_data)
    print("  vault 看板目录  %s" % vault_ledger)
    if a.profile:
        print("  浏览器 profile  %s（tag=%s）" % (a.profile, a.tag or "无"))
    if a.dry:
        print("\n(--dry：只打印，不执行)")

    T = 6
    t0 = time.time()

    # 1 --------------------------------------------------------------
    step(1, T, "抓取收藏（6 平台并发 + TTL 缓存）")
    if a.skip_collect:
        print("  ⏭️  --skip-collect")
    else:
        cmd = [PY, "-u", os.path.join(HERE, "collect_all.py"),
               "--ttl", str(a.ttl)] + (["--force"] if a.force else [])
        if a.profile:
            cmd += ["--profile", a.profile, "--tag", a.tag]
        if not a.dry and sh(cmd).returncode != 0:
            print("  ⚠️ 抓取有失败项（见上），继续跑后续步骤")

    # 2 --------------------------------------------------------------
    step(2, T, "小红书封面（原生 download + 并发，只留第 1 张）")
    if a.skip_covers:
        print("  ⏭️  --skip-covers")
    else:
        cmd = [PY, "-u", os.path.join(HERE, "fetch_covers.py"), "--workers", str(a.workers)]
        if a.force:
            # fetch_covers 自带「已存在即跳过」，--force 时先清空
            cov = os.path.join(HERE, "covers")
            if not a.dry and os.path.isdir(cov):
                print("  --force：清空 %s（%d 张）" % (cov, len(os.listdir(cov))))
                shutil.rmtree(cov, ignore_errors=True)
        if not a.dry:
            sh(cmd)

    # 3 --------------------------------------------------------------
    step(3, T, "归一化 + 分类 → analysis.json")
    if not a.dry:
        sh([PY, "-u", os.path.join(HERE, "analyze_collections.py")])
    aj = os.path.join(coll, "analysis.json")
    if os.path.exists(aj):
        d = json.load(open(aj, encoding="utf-8"))
        pub = sum(1 for i in d["items"] if not i["private"])
        cov = sum(1 for i in d["items"] if (i.get("thumb") or "").startswith("covers/"))
        print("  → 共 %d 条（公开 %d / 隔离 %d），其中小红书本地封面 %d 张"
              % (len(d["items"]), pub, len(d["items"]) - pub, cov))

    # 4 --------------------------------------------------------------
    step(4, T, "建板（工作区 + vault 各一份，封面自动跟过去）")
    if not a.dry:
        sh([PY, "-u", os.path.join(HERE, "build_collections_board.py"), "--out", ws_board])
        if os.path.isdir(vault_ledger):
            sh([PY, "-u", os.path.join(HERE, "build_collections_board.py"), "--out", vault_board])
        else:
            print("  ⚠️ vault 看板目录不存在，跳过：%s" % vault_ledger)

    # 5 --------------------------------------------------------------
    step(5, T, "同步采集数据进 vault（保留 picked.json）")
    if not a.dry:
        sync_to_vault(coll, vault_data, a.dry)
    else:
        sync_to_vault(coll, vault_data, True)

    # 6 --------------------------------------------------------------
    step(6, T, "交付前校验（铁律：0 个 ❌ 才算完成）")
    rc = 0
    if not a.dry:
        rc = sh([PY, "-u", os.path.join(HERE, "verify_board.py")]).returncode
    else:
        print("  (--dry 跳过)")

    print("\n" + "=" * 68)
    print("完成，总耗时 %.1fs" % (time.time() - t0))
    print("  工作区看板  %s" % ws_board)
    print("  vault 看板  %s" % vault_board)
    if rc != 0:
        print("\n🚫 校验未通过 —— **不要交付**，见上面的 ❌ 列表。")
        return rc
    print("\n下一步：present_files 打开看板；若要挑本期精选，用 vault 的 picked.json 去重。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
