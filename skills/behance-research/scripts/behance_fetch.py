#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Behance 取数层 (P0) —— 四条只读命令
=====================================
  search    /search/projects   搜索页（每类页面只 SSR 首屏，翻页参数无效 → 用 field × q 拼池子）
  project   /gallery/<id>      项目详情页
  profile   /<username>        个人/工作室主页
  moodboard /moodboard/<id>    moodboard

设计要点
--------
* 只用标准库，无第三方依赖。
* 解析优先走页面内嵌的 SSR JSON（`<script type="application/json">`），
  失败才退回**语义锚点**（/gallery/<id>/ 的 href、aria-label、screenReaderOnly 文案），
  **不锚定 hash 过的 class 名**，抗改版。
* 输出 JSON 字段与 content-research-board 看板的契约对齐（零胶水直接喂）：
      title / author / cover / url / view / like / publish / rank  ← 看板直接吃
  另加 Behance 专有字段：id / fields / tools / tags / owners / comments

红线：只读抓取；不破解签名、不绕过风控、不逆向内部接口；加请求间隔。
"""

import argparse
import csv
import html as htmlmod
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://www.behance.net"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

_last_request = [0.0]


# ---------------------------------------------------------------- 抓取

def fetch(url, delay=1.5, retries=3, timeout=45):
    """带节流的 GET。url 可为绝对地址或 /path。"""
    if not url.startswith("http"):
        url = BASE + url
    wait = delay - (time.time() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                _last_request[0] = time.time()
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            _last_request[0] = time.time()
            if e.code == 404:
                raise SystemExit(f"[404] 页面不存在（私密 moodboard 未登录时也返回 404）：{url}")
            last_err = e
        except Exception as e:                      # 网络抖动，退避重试
            _last_request[0] = time.time()
            last_err = e
        if attempt < retries - 1:
            time.sleep(2 * (attempt + 1))
    raise SystemExit(f"[抓取失败] {url}\n  {last_err}")


def ssr_json(html_text):
    """取出页面内嵌的最大一块 JSON（Next.js SSR payload）。"""
    blocks = re.findall(
        r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html_text, re.S)
    best_size, best = -1, None
    for b in blocks:
        b = b.strip()
        if not b.startswith("{"):
            continue
        try:
            d = json.loads(b)
        except ValueError:
            continue
        if isinstance(d, dict) and len(b) > best_size:
            best_size, best = len(b), d
    return best


# ---------------------------------------------------------------- 工具

def to_int(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return int(s)
    s = str(s).replace(",", "").strip()
    if not s:
        return None
    mult = 1
    if s[-1:].upper() in ("K", "M"):
        mult = 1000 if s[-1:].upper() == "K" else 1000000
        s = s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return None


def iso(ts):
    if not ts:
        return None
    try:
        return time.strftime("%Y-%m-%d", time.gmtime(int(ts)))
    except Exception:
        return None


def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", htmlmod.unescape(s)).strip()


def pick_img(node, sizes=("size_original", "size_disp", "size_max_1200", "url")):
    """从 Behance 的图片对象里挑一个 url。"""
    if not isinstance(node, dict):
        return None
    for k in sizes:
        v = node.get(k)
        if isinstance(v, dict) and v.get("url"):
            return v["url"]
        if isinstance(v, str) and v.startswith("http"):
            return v
    for v in node.values():
        if isinstance(v, dict) and v.get("url"):
            return v["url"]
    return None


def cover_variant(url, size):
    """把封面 URL 换成另一档尺寸：/projects/404/<hash> → /projects/<size>/<hash>。"""
    if not url or not size:
        return url
    return re.sub(r"(/projects/)[^/]+(/[^/]+)$", r"\g<1>%s\g<2>" % size, url)


# ---------------------------------------------------------------- search

_CARD = re.compile(r'<div aria-label="([^"]*)" class="ProjectCoverNeue-root-')
_HREF = re.compile(r'href="/gallery/(\d+)/([^?"]+)')
_COVER = re.compile(
    r'<img[^>]*src="(https://mir-s3-cdn-cf\.behance\.net/projects/[^"]+)"[^>]*js-cover-image')
_COVER_ANY = re.compile(r'<img[^>]*src="(https://mir-s3-cdn-cf\.behance\.net/projects/[^"]+)"')
# 领域 ribbon：href 形如 /galleries/3d-art/3d-art（两段同名）；工具 ribbon 形如 /galleries/Photoshop（单段）
_FIELD = re.compile(r'href="https://www\.behance\.net/galleries/([^/"?]+)/([^/"?]+)"[^>]*aria-label="([^"]+)"')
# 作者：锚在 data-axe="owners-target-size" 容器里的外链
_OWNER_BLOCK = re.compile(r'data-axe="owners-target-size"(.*?)</div>\s*</div>\s*</div>', re.S)
_OWNER_A = re.compile(r'<a href="https://www\.behance\.net/([^/?"]+)\?[^"]*"[^>]*>([^<]+)</a>')
_APPR = re.compile(r'>([\d,]+)\s*appreciations for')
_VIEWS = re.compile(r'>([\d,]+)\s*views for')
_TITLE_LINK = re.compile(r'href="https://www\.behance\.net/gallery/(\d+)/([^?"]+)\?[^"]*"\s*class="Title-title')


def parse_search(html_text, field=None, query=None):
    marks = list(_CARD.finditer(html_text))
    items = []
    seen = set()
    for i, m in enumerate(marks):
        name = htmlmod.unescape(m.group(1)).strip()
        block = html_text[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(html_text)]
        href = _HREF.search(block)
        if not href:
            continue
        pid, slug = href.group(1), href.group(2)
        if pid in seen:
            continue
        seen.add(pid)

        cover = _COVER.search(block) or _COVER_ANY.search(block)
        owners = []
        ob = _OWNER_BLOCK.search(block)
        if ob:
            owners = [{"username": u, "name": htmlmod.unescape(n).strip()}
                      for u, n in _OWNER_A.findall(ob.group(1))]
        fields = []
        for a, b, label in _FIELD.findall(block):
            if a == b and label not in fields:          # 两段同名 → 领域
                fields.append(label)
        ap = _APPR.search(block)
        vw = _VIEWS.search(block)

        items.append({
            # —— 与 content-research-board 看板对齐的契约字段 ——
            "rank": len(items) + 1,
            "title": name,
            "author": owners[0]["name"] if owners else None,
            "cover": cover.group(1) if cover else None,
            "url": f"{BASE}/gallery/{pid}/{slug}",
            "view": to_int(vw.group(1)) if vw else None,
            "like": to_int(ap.group(1)) if ap else None,
            "publish": None,
            "source": "behance/search",
            # —— Behance 专有 ——
            "id": int(pid),
            "slug": slug,
            "owners": owners,
            "fields": fields,
            "search_field": field,
            "search_query": query,
        })
    return items


def cmd_search(a):
    """实测（2026-09-19）：关键词参数是 `search=`，不是 `q=`。
    `?q=xxx` 会被静默忽略；`field=` 与 `search=` 可叠加，且叠加后确实返回新结果。
    翻页参数（page / sort / time / owners）仍全部无效。"""
    qs = {}
    if a.field:
        qs["field"] = a.field
    if a.search:
        qs["search"] = a.search
    url = "/search/projects" + ("?" + urllib.parse.urlencode(qs) if qs else "")
    html_text = fetch(url, a.delay)
    items = parse_search(html_text, a.field, a.search)
    top = {"kind": "search", "url": BASE + url, "field": a.field,
           "query": a.search, "count": len(items),
           "note": "只 SSR 首屏（约 24 条）；翻页无效。切分维度＝field= × search=。",
           "items": items[: a.limit] if a.limit else items}
    return top


# ---------------------------------------------------------------- project

def project_from_html(html_text, fallback_id=None):
    """把项目页 HTML 解析成结构化 dict（供脚本复用，不必走 CLI）。"""
    d = ssr_json(html_text)
    pr = (d or {}).get("project", {}).get("project")
    if not pr:
        raise SystemExit("[解析失败] 没在项目页里找到 project 对象，页面可能改版。")
    st = pr.get("stats") or {}
    owners = [{"username": o.get("username"), "name": o.get("displayName"),
               "url": o.get("url")} for o in (pr.get("owners") or [])]
    mods = pr.get("allModules") or pr.get("modules") or []
    covers = (pr.get("covers") or {}).get("allAvailable") or []
    return {
        "kind": "project",
        # —— 看板契约 ——
        "rank": 1,
        "title": pr.get("name"),
        "author": owners[0]["name"] if owners else None,
        "cover": pick_img(covers[0]) if covers else None,
        "url": pr.get("url"),
        "view": (st.get("views") or {}).get("all"),
        "like": (st.get("appreciations") or {}).get("all"),
        "publish": iso(pr.get("publishedOn")),
        "source": "behance/project",
        # —— 专有 ——
        "id": pr.get("id") or fallback_id,
        "owners": owners,
        "fields": [f.get("name") for f in (pr.get("features") or [])],
        "tools": [t.get("title") for t in (pr.get("tools") or [])],
        "tags": [t.get("title") for t in (pr.get("tags") or [])],
        "comments": (st.get("comments") or {}).get("all"),
        "published_ts": pr.get("publishedOn"),
        "description": strip_tags(pr.get("description")),
        "license": (pr.get("license") or {}).get("license"),
        "module_count": len(mods),
        "modules": [{"id": m.get("id"),
                     "type": m.get("type"),
                     "caption": strip_tags(m.get("caption")),
                     "image": pick_img(m.get("imageSizes") or m),
                     "video": (m.get("video") or {}).get("url")} for m in mods],
        "all_covers": [c.get("url") for c in covers],
    }


def cmd_project(a):
    target = a.target
    if target.isdigit():
        # 只给 id 时 Behance 需要 slug 才响应；实测 /gallery/<id>/x 返回 200 且按 id 解析
        target = f"/gallery/{target}/x"
    elif not target.startswith("http"):
        target = "/gallery/" + target.lstrip("/")
    html_text = fetch(target, a.delay)
    pid = re.search(r"/gallery/(\d+)", target)
    return project_from_html(html_text, pid.group(1) if pid else None)


# ---------------------------------------------------------------- profile

def cmd_profile(a):
    """个人主页（profile.user）与工作室/团队主页（team.profile）两种结构都吃。
    两者都在 HTML 里渲染首屏项目卡（约 12 个），用同一套卡片解析器顺带取回。"""
    user = a.target.rstrip("/").split("/")[-1].split("?")[0]
    html_text = fetch("/" + user, a.delay)
    d = ssr_json(html_text) or {}
    u = (d.get("profile") or {}).get("user")
    kind = "profile"
    if not u:
        u = (d.get("team") or {}).get("profile")
        kind = "team"
    if not u:
        raise SystemExit("[解析失败] 主页里既没有 profile.user 也没有 team.profile，页面可能改版。")

    def g(*keys):
        """兼容个人页 camelCase 与团队页 snake_case。"""
        for k in keys:
            if u.get(k) not in (None, "", []):
                return u[k]
        return None

    st = u.get("stats") or {}
    stats = {
        "views": to_int(st.get("views")),
        "appreciations": to_int(st.get("appreciations")),
        "followers": to_int(st.get("followers")),
        "following": to_int(st.get("following")),
    }
    if kind == "team":
        stats["members"] = to_int(st.get("members"))
        stats["projects"] = to_int(st.get("projects"))

    # 团队页的卡是另一套布局（HTML 里只 SSR 一部分），优先用 JSON 里的 projects 列表；
    # 个人页则用 HTML 卡片（JSON 里没有项目列表）。
    json_projects = u.get("projects") if kind == "team" else None
    if isinstance(json_projects, list) and json_projects:
        projects = []
        for i, p in enumerate(json_projects, 1):
            covers = p.get("covers") or {}
            cover = covers.get("404") or covers.get("max_1200") or \
                (next(iter(covers.values())) if covers else None)
            projects.append({
                "rank": i,
                "title": p.get("name"),
                "author": g("displayName", "display_name", "name"),
                "cover": cover,
                "url": p.get("url"),
                "view": None,
                "like": None,
                "publish": iso(p.get("published_on")),
                "source": "behance/team",
                "id": p.get("id"),
                "slug": p.get("slug"),
                "fields": p.get("fields") or [],
                "privacy": p.get("privacy"),
            })
    else:
        projects = parse_search(html_text)

    return {
        "kind": kind,
        "username": g("username", "slug"),
        "name": g("displayName", "display_name", "name"),
        "url": f"{BASE}/{g('username', 'slug')}",
        "occupation": g("occupation"),
        "company": g("company"),
        "location": g("location"),
        "website": g("website"),
        "created": iso(g("createdOn", "created_on")),
        "created_ts": g("createdOn", "created_on"),
        "stats": stats,
        "fields": [f.get("name") or f.get("label")
                   for f in ((u.get("features") or u.get("field_links") or []))],
        "teams": [{"name": t.get("name"), "url": t.get("url"),
                   "location": t.get("location")} for t in (u.get("teams") or [])],
        "web_links": [{"title": w.get("title"), "name": w.get("name"), "url": w.get("url")}
                      for w in (u.get("webLinks") or u.get("links") or [])],
        "social_links": [{"service": s.get("socialService"), "url": s.get("url")}
                         for s in (u.get("socialReferences") or u.get("social_links") or [])],
        "work_experiences": [{"company": w.get("company"), "position": w.get("position")}
                             for w in (u.get("workExperiences") or [])],
        "members": [{"name": m.get("display_name") or m.get("displayName"),
                     "username": m.get("username"), "occupation": m.get("occupation")}
                    for m in (u.get("members") or [])],
        "projects": projects,
        "project_count": len(projects),
        "note": "项目列表只有首屏（约 12 个）；主页翻页参数无效。",
    }


# ---------------------------------------------------------------- moodboard

def cmd_moodboard(a):
    target = a.target
    if target.isdigit():
        target = f"/moodboard/{target}/x"
    elif not target.startswith("http"):
        target = "/moodboard/" + target.lstrip("/")
    html_text = fetch(target, a.delay)
    d = ssr_json(html_text)
    c = (d or {}).get("collection")
    if not c:
        raise SystemExit("[解析失败] 没在 moodboard 页里找到 collection 对象。")
    items = []
    for it in (c.get("items") or []):
        imgs = it.get("images") or []
        src = None
        if imgs:
            src = imgs[-1].get("url") if isinstance(imgs[-1], dict) else None
        ent = it.get("entity") or {}
        items.append({
            "rank": len(items) + 1,
            "title": ent.get("name") or it.get("name"),
            "author": ((ent.get("owners") or [{}])[0].get("displayName")
                       if ent.get("owners") else it.get("owner", {}).get("displayName")
                       if isinstance(it.get("owner"), dict) else None),
            "cover": src or pick_img(ent.get("covers", {}).get("allAvailable", [{}])[0]
                                     if ent.get("covers") else None),
            "url": ent.get("url") or (f"{BASE}/gallery/{it.get('id')}/{it.get('slug')}"
                                      if it.get("id") else None),
            "view": ((ent.get("stats") or {}).get("views") or {}).get("all"),
            "like": ((ent.get("stats") or {}).get("appreciations") or {}).get("all"),
            "publish": None,
            "source": "behance/moodboard",
            "id": it.get("id"),
            "entity_type": it.get("entityType"),
            "owners": ent.get("owners"),
            "fields": [f.get("name") for f in (ent.get("features") or [])],
        })
    return {
        "kind": "moodboard",
        "id": c.get("collectionId"),
        "title": c.get("title"),
        "url": BASE + (c.get("url") or target),
        "is_public": c.get("isCollectionPublic"),
        "stats": c.get("stats"),
        "is_last_page": c.get("isItemsLastPage"),
        "next_cursor": c.get("itemsLastCursor"),
        "count": len(items),
        "note": "未登录只 SSR 首批；isItemsLastPage=false 说明还有更多，需登录态或分批。",
        "items": items,
    }


# ---------------------------------------------------------------- 输出

def write_csv(path, items, fields):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for it in items:
            row = dict(it)
            for k, v in list(row.items()):
                if isinstance(v, (list, dict)):
                    row[k] = json.dumps(v, ensure_ascii=False)
            w.writerow(row)


CSV_FIELDS = ["rank", "id", "title", "author", "url", "cover", "view", "like",
              "comments", "publish", "fields", "tools", "tags", "module_count",
              "search_field", "search_query", "source"]


def emit(data, args):
    out = args.out
    if not out:
        out = {"search": "search.json", "project": "project.json",
               "profile": "profile.json", "moodboard": "moodboard.json"}[data["kind"]]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    items = data.get("items") or data.get("projects") or [data]
    if args.csv:
        write_csv(args.csv, items, CSV_FIELDS)
    # 摘要到 stderr，JSON 结果到 stdout（方便管道）
    n = len(items)
    extra = ""
    if data["kind"] in ("profile", "team") and isinstance(data.get("stats"), dict):
        extra = "  统计：" + json.dumps(data["stats"], ensure_ascii=False)
    print(f"[behance/{data['kind']}] {n} 项 → {out}"
          + (f"  +  {args.csv}" if args.csv else "") + extra, file=sys.stderr)
    if data["kind"] == "search":
        for it in items[:8]:
            print(f"   #{it['rank']:<2} {str(it['like'] or 0):>6}♡ "
                  f"{str(it['view'] or 0):>7}👁  {it['title'][:46]}", file=sys.stderr)
    elif data["kind"] in ("profile", "team"):
        for it in items:
            print(f"   - {str(it['like'] or 0):>6}♡ {str(it['view'] or 0):>7}👁  "
                  f"{it['title'][:48]}", file=sys.stderr)
    elif data["kind"] == "moodboard":
        for it in items:
            print(f"   - {it['title']}  ·  {it['author']}", file=sys.stderr)
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(
        description="Behance 取数层（只读）", formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="例：\n  %(prog)s search --field '3D Art' -o data/3d-art.json --csv data/3d-art.csv\n"
               "  %(prog)s project 245233547\n  %(prog)s profile seth_liao\n"
               "  %(prog)s moodboard 226764113\n")
    ap.add_argument("--delay", type=float, default=1.5, help="请求间隔秒，默认 1.5")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="搜索页")
    s.add_argument("--field", help="领域筛选，如 '3d art'（唯一有效的切分维度）")
    s.add_argument("-s", "--search", "--q", dest="search",
                   help="关键词（参数名是 search=；q= 会被 Behance 静默忽略）")
    s.add_argument("--limit", type=int, help="只保留前 N 条")
    s.add_argument("-o", "--out")
    s.add_argument("--csv")
    s.set_defaults(func=cmd_search)

    for nm, fn, hlp in (("project", cmd_project, "项目页（id 或 URL）"),
                        ("profile", cmd_profile, "个人/工作室主页（username）"),
                        ("moodboard", cmd_moodboard, "moodboard（id 或 URL）")):
        p = sub.add_parser(nm, help=hlp)
        p.add_argument("target")
        p.add_argument("-o", "--out")
        p.add_argument("--csv")
        p.set_defaults(func=fn)

    a = ap.parse_args()
    emit(a.func(a), a)


if __name__ == "__main__":
    main()
