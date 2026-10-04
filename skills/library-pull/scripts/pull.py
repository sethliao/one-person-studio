#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 WorkBuddy 资料库批量取回节点到本地。

用法:
    LIB_TOK="<token>" python3 pull.py --spec spec.json --out /tmp/pull

spec.json:
{
  "items": [
    {"path": "工具/SKILL.md",   "node_id": "xxxx", "kind": "doc"},
    {"path": "工具/run.py",     "node_id": "yyyy", "kind": "smh"},
    {"path": "工具/report.html","node_id": "zzz",  "kind": "web"}
  ]
}

输出目录布局:
    <out>/<path>.raw   doc 节点的原始组件语法正文（喂给 convert.py）
    <out>/<path>       smh / drive 文件本体
    <out>/<path>       web 节点的 html 产物（只取 .html）

token 通过环境变量 LIB_TOK 或 stdin 首行传入（配合 --token-stdin）。
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

SKILL = os.environ.get(
    "LIBRARY_SKILL_DIR",
    os.path.expanduser(
        "~/Library/Caches/com.tencent.workbuddy.mac.BundleMigration/backups/"
        "WorkBuddy-5.5.4.38151288-1788946749595.backup.app/Contents/Resources/app.asar.unpacked/"
        "resources/plugins/workbuddy-builtin/skills/library"),
)
UA = {"User-Agent": "Mozilla/5.0"}


def get_token(args):
    if args.token_stdin:
        return sys.stdin.readline().strip()
    tok = os.environ.get("LIB_TOK")
    if not tok:
        sys.exit("缺少 token：设置 LIB_TOK 或传 --token-stdin")
    return tok


def run(script, token, *args):
    cmd = ["python3", f"{SKILL}/{script}", "--token-stdin", *args]
    p = subprocess.run(cmd, input=token, capture_output=True, text=True)
    return p.stdout


def kv_line(out, prefix):
    """KS_XXX\\tpayload 或 KS_XXX payload（不解析 JSON，只还原 payload 文本）"""
    for line in out.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip("\t ").rstrip()
    return None


def fetch_doc(token, node_id, dst):
    out = run("doc/get_doc_reviews.py", token, "--page-id", node_id)
    if not out.strip() or out.lstrip().startswith('{"error"'):
        return f"✗ {node_id} doc 读取失败: {out.strip()[:120]}"
    with open(dst + ".raw", "w", encoding="utf-8") as f:
        f.write(out)
    return f"✓ {os.path.basename(dst)}.raw {len(out)}B"


def fetch_smh(token, node_id, dst):
    out = run("smh/get_download_link.py", token, "--node-id", node_id)
    body = kv_line(out, "KS_SMH_DOWNLOAD")
    if not body:
        return f"✗ {node_id} smh 未取到下载链接: {out.strip()[:120]}"
    meta = json.loads(body)
    req = urllib.request.Request(meta["download_url"], headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(dst, "wb") as f:
        f.write(r.read())
    return f"✓ {os.path.basename(dst)} {os.path.getsize(dst)}B"


def fetch_web(token, node_id, dst):
    out = run("page/list_page_artifacts.py", token, "--node-id", node_id)
    data = None
    for cand in (out, *out.splitlines()):
        try:
            data = json.loads(cand)["data"]
            break
        except Exception:
            continue
    if not data:
        return f"✗ {node_id} web 产物列表失败: {out.strip()[:120]}"
    base = data["url"]
    got = []
    for a in data.get("artifacts", []):
        if not a["path"].endswith(".html"):
            continue
        target = dst if dst.endswith(".html") else f"{dst}.html"
        req = urllib.request.Request(base + a["path"], headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r, open(target, "wb") as f:
            f.write(r.read())
        got.append(f"{os.path.basename(target)} {os.path.getsize(target)}B")
    return "✓ " + ", ".join(got) if got else f"✗ {node_id} 无 html 产物"


HANDLERS = {"doc": fetch_doc, "smh": fetch_smh, "drive": fetch_smh, "web": fetch_web}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--token-stdin", action="store_true")
    args = ap.parse_args()

    token = get_token(args)
    spec = json.load(open(args.spec, encoding="utf-8"))
    items = spec.get("items", spec if isinstance(spec, list) else [])
    os.makedirs(args.out, exist_ok=True)

    ok = fail = 0
    for it in items:
        kind = it["kind"]
        dst = os.path.join(args.out, it["path"])
        os.makedirs(os.path.dirname(dst) or args.out, exist_ok=True)
        handler = HANDLERS.get(kind)
        if not handler:
            print(f"✗ 不支持的 kind: {kind} ({it['path']})")
            fail += 1
            continue
        try:
            msg = handler(token, it["node_id"], dst)
        except Exception as e:
            msg = f"✗ {it['path']} 异常: {e}"
        print(msg)
        ok += not msg.startswith("✗")
        fail += msg.startswith("✗")

    print(f"\n成功 {ok} · 失败 {fail}")


if __name__ == "__main__":
    main()
