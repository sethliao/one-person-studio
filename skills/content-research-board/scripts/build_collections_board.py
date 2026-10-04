#!/usr/bin/env python3
"""收藏总账看板生成器。

从 data/collect/analysis.json 生成单页 HTML 看板：
  统计条 → 主题分布 → 跨平台共鸣矩阵 → 可筛选卡片墙 → 隐私桶（折叠隔离）

用法： python3 build_collections_board.py [--out collections-board.html] [--page 48]
"""
import json, os, argparse, html
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))


def _find_coll():
    cands = [
        os.path.join(HERE, "data", "collect"),
        os.path.join(HERE, "..", "data", "collect"),
        os.path.join(HERE, "..", "collections-ledger", "data", "collect"),
        os.path.join(os.getcwd(), "data", "collect"),
    ]
    for c in cands:
        if os.path.isdir(c):
            return os.path.abspath(c)
    return os.path.abspath(cands[0])


COLL = _find_coll()

PLAT_ORDER = ["B站", "小红书", "YouTube", "微博", "知乎", "Pinterest", "X", "GitHub", "Behance"]
PLAT_COLOR = {
    "B站": "#00A1D6", "小红书": "#FF2442", "YouTube": "#FF0000", "微博": "#E6162D",
    "知乎": "#0084FF", "Pinterest": "#BD081C", "X": "#111111", "GitHub": "#24292F",
    "Behance": "#1769FF",
}
# metric 的语义单位（不同平台的「热度」不是同一个东西，必须标出来）
METRIC_UNIT = {
    "B站": "播放", "小红书": "点赞", "YouTube": "views", "微博": "点赞",
    "知乎": "赞同", "Pinterest": "收藏", "X": "赞", "GitHub": "stars", "Behance": "浏览",
}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def _default_out():
    """默认输出：优先 vault 的 003-Workbench/collections-ledger/，否则脚本同级。"""
    led = os.path.join(HERE, "..", "collections-ledger")
    if os.path.isdir(led):
        return os.path.abspath(os.path.join(led, "collections-board.html"))
    return os.path.join(HERE, "collections-board.html")


def _sync_covers(out_path, items):
    """把本地封面同步到看板同级 covers/ —— 看板用相对路径引用，file:// 双击也能看。"""
    import shutil
    src = None
    for c in [os.path.join(HERE, "covers"),
              os.path.join(os.path.dirname(COLL), "covers"),
              os.path.join(os.getcwd(), "covers")]:
        if os.path.isdir(c):
            src = c
            break
    if not src:
        return 0, 0
    need = {(i.get("thumb") or "").split("/")[-1] for i in items
            if (i.get("thumb") or "").startswith("covers/")}
    if not need:
        return 0, 0
    dst = os.path.join(os.path.dirname(os.path.abspath(out_path)), "covers")
    os.makedirs(dst, exist_ok=True)
    n = 0
    for f in sorted(need):
        s = os.path.join(src, f)
        d = os.path.join(dst, f)
        if os.path.exists(s) and not (os.path.exists(d) and os.path.getsize(d) == os.path.getsize(s)):
            shutil.copyfile(s, d)
        if os.path.exists(d):
            n += 1
    return n, len(need)


def build(out_path, page_size):
    d = json.load(open(os.path.join(COLL, "analysis.json"), encoding="utf-8"))
    items = d["items"]
    public = [i for i in items if not i["private"]]
    private = [i for i in items if i["private"]]
    theme_cn = d["theme_cn"]

    # 平台计数（只算公开）
    plat_n = Counter(i["platform"] for i in public)
    plats = [p for p in PLAT_ORDER if plat_n.get(p)] + [p for p in plat_n if p not in PLAT_ORDER]

    # 主题计数（只算公开）
    th_n = Counter()
    for i in public:
        for t in i["themes"]:
            th_n[t] += 1
    themes = [(t, n) for t, n in th_n.most_common()]
    th_max = max([n for _, n in themes] or [1])

    # 主题 × 平台矩阵
    mat = {}
    for i in public:
        for t in i["themes"]:
            mat.setdefault(t, Counter())[i["platform"]] += 1
    mat_max = max([max(c.values()) for c in mat.values()] or [1])

    # 隐私桶按平台计数
    pv_n = Counter(i["platform"] for i in private)

    # 卡片数据（精简字段，减小体积）
    def slim(i):
        return {
            "p": i["platform"], "g": i["group"], "t": (i["title"] or "")[:220],
            "a": i["author"][:70], "u": i["url"], "m": i["metric"], "d": i["date"][:24],
            "e": i["extra"][:170], "th": i["thumb"], "tp": i["theme_primary"],
            "ts": i["themes"],
        }
    data_json = json.dumps({
        "items": [slim(i) for i in public],
        "themeCn": theme_cn,
        "pageSize": page_size,
    }, ensure_ascii=False, separators=(",", ":"))

    def plat_chips():
        rows = ['<button class="chip on" data-p="all">全部 <b>%d</b></button>' % len(public)]
        for p in plats:
            rows.append('<button class="chip" data-p="%s"><i style="background:%s"></i>%s <b>%d</b></button>'
                        % (esc(p), PLAT_COLOR.get(p, "#888"), esc(p), plat_n[p]))
        return "\n      ".join(rows)

    def theme_chips():
        rows = ['<button class="chip on" data-t="all">全部主题</button>']
        for t, n in themes:
            rows.append('<button class="chip" data-t="%s">%s <b>%d</b></button>'
                        % (esc(t), esc(theme_cn.get(t, t)), n))
        return "\n      ".join(rows)

    def theme_bars():
        rows = []
        for t, n in themes:
            w = round(100 * n / th_max, 2)
            rows.append(
                '<div class="bar"><span class="bl">%s</span>'
                '<span class="bt"><i style="width:%.2f%%"></i></span>'
                '<span class="bn">%d</span></div>' % (esc(theme_cn.get(t, t)), w, n))
        return "\n      ".join(rows)

    def matrix():
        head = "".join('<th><span>%s</span></th>' % esc(p) for p in plats)
        body = []
        for t, _ in themes:
            if t in d["private_themes"]:
                continue
            cells = []
            for p in plats:
                n = mat.get(t, Counter()).get(p, 0)
                a = n / mat_max if mat_max else 0
                style = "" if not n else "background:rgba(194,84,47,%.3f);color:%s" % (
                    min(0.10 + a * 0.72, 0.86), "#fff" if a > 0.5 else "#17181A")
                cells.append('<td style="%s">%s</td>' % (style, n or ""))
            tag = ' <span class="pv">隐私</span>' if t in d["private_themes"] else ""
            body.append('<tr><th>%s</th>%s</tr>' % (esc(theme_cn.get(t, t)) + tag, "".join(cells)))
        return ('<div class="tw"><table class="mat"><thead><tr><th></th>%s</tr></thead><tbody>%s</tbody></table></div>'
                % (head, "\n".join(body)))

    def private_block():
        if not private:
            return ""
        rows = []
        for i in private[:28]:
            rows.append('<li><span class="pp">%s</span>%s</li>'
                        % (esc(i["platform"]), esc((i["title"] or i["extra"])[:96])))
        more = '<li class="more">…另有 %d 条</li>' % (len(private) - 28) if len(private) > 28 else ""
        return """
  <section class="sec">
    <details class="priv">
      <summary><span class="warn">⚠</span> 已隔离 %d 条（医疗 / 心理 / 个人隐私）</summary>
      <p class="pn">这类内容已被自动识别并<strong>排除在主题统计与选题建议之外</strong>。以下仅列出条目名与来源平台，供你自己核对是否有误判；不生成缩略图、不做内容分析。</p>
      <ul class="pl">%s%s</ul>
      <p class="pn">来源分布：%s</p>
    </details>
  </section>""" % (len(private), "\n".join(rows), more,
                     "、".join("%s %d" % (p, n) for p, n in pv_n.most_common()))

    tpl = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>收藏总账 · 九平台横向分析</title>
<style>
:root{
  --paper:#FBFAF8; --card:#FFFFFF; --ink:#17181A; --ink2:#3C3E44; --mut:#74767D;
  --line:#E6E3DD; --line2:#D8D4CB; --acc:#C2542F; --acc2:#8C3A1E; --pv:#8A6D3B;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);
  font:15px/1.62 "PingFang SC","Hiragino Sans GB","Microsoft YaHei",-apple-system,"Segoe UI",sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1240px;margin:0 auto;padding:52px 30px 96px}
.serif{font-family:ui-serif,Georgia,"Songti SC","Noto Serif SC",serif}

/* ---- header ---- */
header{margin-bottom:44px}
.kicker{font-size:11.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--mut);font-weight:600}
h1{font-size:40px;line-height:1.16;margin:14px 0 12px;font-weight:600;letter-spacing:-.015em}
h1 em{font-style:normal;color:var(--acc)}
.lede{max-width:720px;color:var(--ink2);font-size:15.5px;margin:0}
.lede b{color:var(--ink)}
.stamp{margin-top:20px;font-size:12.5px;color:var(--mut);
  display:flex;gap:22px;flex-wrap:wrap;border-top:1px solid var(--line);padding-top:16px}
.stamp span b{color:var(--ink);font-weight:600}

/* ---- sections ---- */
.sec{margin:0 0 52px}
h2{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--mut);
  font-weight:700;margin:0 0 6px}
h2+.sub{font-size:19px;font-weight:600;margin:0 0 20px;letter-spacing:-.01em}
h2+.sub .num{color:var(--acc)}

/* ---- bars ---- */
.bars{display:grid;gap:7px;max-width:760px}
.bar{display:grid;grid-template-columns:150px 1fr 46px auto;gap:12px;align-items:center;font-size:13.5px}
.bl{color:var(--ink2);text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bt{height:15px;background:#EFECE6;border-radius:2px;overflow:hidden;display:block}
.bt i{display:block;height:100%;background:linear-gradient(90deg,var(--acc),#D97A55);border-radius:2px}
.bn{font-variant-numeric:tabular-nums;color:var(--mut);font-size:12.5px;text-align:right}
.pv{font-size:10px;letter-spacing:.06em;color:var(--pv);border:1px solid #E0D3B8;
  background:#FBF6EA;border-radius:3px;padding:1px 5px;white-space:nowrap}

/* ---- matrix ---- */
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:8px;background:var(--card)}
table.mat{border-collapse:collapse;width:100%;font-size:12.5px;min-width:760px}
table.mat th,table.mat td{padding:8px 6px;text-align:center;border-bottom:1px solid var(--line)}
table.mat thead th{font-weight:600;color:var(--mut);font-size:11.5px;background:#F6F4F0;
  border-bottom:1px solid var(--line2);position:sticky;top:0}
table.mat thead th span{writing-mode:horizontal-tb;white-space:nowrap}
table.mat tbody th{text-align:right;font-weight:500;color:var(--ink2);white-space:nowrap;
  padding-right:14px;background:var(--card);border-right:1px solid var(--line)}
table.mat td{font-variant-numeric:tabular-nums;color:transparent;width:64px}
table.mat tbody tr:last-child td,table.mat tbody tr:last-child th{border-bottom:none}

/* ---- filters ---- */
.tools{position:sticky;top:0;z-index:20;background:rgba(251,250,248,.94);
  backdrop-filter:blur(10px);border-bottom:1px solid var(--line);margin:0 -30px 24px;padding:14px 30px 12px}
.chips{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:9px;align-items:center}
.chip{font:inherit;font-size:12.5px;border:1px solid var(--line2);background:var(--card);
  color:var(--ink2);border-radius:999px;padding:4px 11px;cursor:pointer;display:inline-flex;
  align-items:center;gap:6px;transition:.13s}
.chip:hover{border-color:var(--ink2);color:var(--ink)}
.chip.on{background:var(--ink);border-color:var(--ink);color:#fff}
.chip b{font-weight:600;opacity:.6;font-variant-numeric:tabular-nums}
.chip i{width:7px;height:7px;border-radius:50%;display:inline-block}
.row2{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
input[type=search]{font:inherit;font-size:13.5px;border:1px solid var(--line2);border-radius:7px;
  padding:7px 12px;background:var(--card);color:var(--ink);min-width:260px;flex:1;max-width:400px}
input[type=search]:focus{outline:2px solid rgba(194,84,47,.28);border-color:var(--acc)}
select{font:inherit;font-size:13px;border:1px solid var(--line2);border-radius:7px;padding:7px 10px;
  background:var(--card);color:var(--ink2);cursor:pointer}
.count{font-size:12.5px;color:var(--mut);margin-left:auto;font-variant-numeric:tabular-nums}

/* ---- grid：瀑布流（CSS columns）—— 保留图片原始比例，不裁剪 ---- */
.grid{columns:4 268px;column-gap:18px}
.grid .card{break-inside:avoid;-webkit-column-break-inside:avoid;page-break-inside:avoid;
  margin:0 0 18px;display:inline-block;width:100%}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;
  transition:.16s}
.card:hover{border-color:var(--line2);box-shadow:0 5px 20px -8px rgba(23,24,26,.16);transform:translateY(-2px)}
.thumb{background:#F2F0EB;overflow:hidden;display:block;position:relative;min-height:64px}
.thumb img{width:100%;height:auto;display:block}
.thumb.no{aspect-ratio:16/10}
.thumb.no img{display:none}
.thumb.no::after{content:attr(data-p);position:absolute;inset:0;display:flex;align-items:center;
  justify-content:center;font-size:11.5px;letter-spacing:.02em;color:#A9A49A;font-weight:500;
  padding:0 18px;text-align:center}
.body{padding:13px 14px 15px;display:flex;flex-direction:column;gap:9px}
.meta{display:flex;gap:7px;align-items:center;font-size:11px;flex-wrap:wrap}
.badge{font-size:10.5px;font-weight:600;padding:2px 7px;border-radius:4px;color:#fff;letter-spacing:.02em}
.grp{color:var(--mut);font-size:11px}
.tt{font-size:14px;line-height:1.5;font-weight:500;color:var(--ink);margin:0;
  display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;word-break:break-word}
.au{font-size:11.5px;color:var(--mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tags{display:flex;gap:5px;flex-wrap:wrap}
.tag{font-size:10.5px;color:var(--ink2);background:#F4F2ED;border-radius:3px;padding:2px 6px;white-space:nowrap}
.foot{display:flex;justify-content:space-between;align-items:center;
  border-top:1px solid var(--line);padding-top:10px;font-size:11.5px;color:var(--mut)}
.go{color:var(--acc);text-decoration:none;font-weight:600;white-space:nowrap}
.go:hover{text-decoration:underline}
.metric{font-variant-numeric:tabular-nums;color:var(--mut);font-size:11.5px}
.metric em{font-style:normal;font-weight:600;color:var(--ink2)}
.more,.empty{column-span:all;text-align:center;padding:8px}
.empty{color:var(--mut);padding:70px 0;font-size:14px}
.more button{font:inherit;font-size:13.5px;font-weight:600;border:1px solid var(--line2);
  background:var(--card);color:var(--ink);border-radius:8px;padding:11px 30px;cursor:pointer}
.more button:hover{border-color:var(--ink);background:var(--ink);color:#fff}

/* ---- private ---- */
.priv{border:1px solid #E3D9C4;background:#FDFBF5;border-radius:10px;padding:16px 20px}
.priv summary{cursor:pointer;font-weight:600;font-size:14px;color:#6B5729;list-style:none}
.priv summary::-webkit-details-marker{display:none}
.priv summary::before{content:"▸";display:inline-block;margin-right:8px;transition:.15s;color:#9C8451}
.priv[open] summary::before{transform:rotate(90deg)}
.warn{color:#B8860B}
.pn{font-size:12.5px;color:#7A6A45;margin:12px 0 10px;line-height:1.65}
.pn strong{color:#5A4A22}
.pl{list-style:none;padding:0;margin:0;display:grid;gap:5px;max-height:340px;overflow:auto}
.pl li{font-size:12.5px;color:#6B5729;display:flex;gap:9px;align-items:baseline;padding:3px 0}
.pp{font-size:10px;font-weight:600;color:#8A7442;background:#F2EAD6;border-radius:3px;
  padding:1px 6px;white-space:nowrap;flex:none}
.pl .more{color:#9C8451;font-style:italic}

footer{border-top:1px solid var(--line);padding-top:22px;margin-top:16px;
  font-size:12px;color:var(--mut);line-height:1.8}
footer code{background:#F2F0EB;padding:1px 5px;border-radius:3px;font-size:11.5px}
@media(max-width:720px){
  .wrap{padding:32px 18px 70px}
  h1{font-size:29px}
  .tools{margin:0 -18px 20px;padding:12px 18px 10px}
  .bar{grid-template-columns:104px 1fr 34px auto;font-size:12px}
  .grid{columns:1;column-gap:0}
  .count{margin-left:0;width:100%}
}
</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="kicker">Collection Ledger · 九平台</div>
  <h1>我在九平台上<br>到底<em>收藏了什么</em></h1>
  <p class="lede">把散落在 B站、小红书、YouTube、微博、知乎、Pinterest、X、GitHub、Behance 的收藏、点赞、稍后再看、Star 和 Pin 合成一本总账，用同一套主题词表分类。<b>每一条都能点回原始出处</b>；医疗与个人隐私类内容已自动隔离，不参与统计与建议。</p>
  <div class="stamp">
    <span>总条目 <b id="sTotal">0</b></span>
    <span>平台 <b id="sPlat">0</b></span>
    <span>主题 <b id="sTheme">0</b></span>
    <span>有缩略图 <b id="sThumb">0</b></span>
    <span>已隔离隐私 <b>__PV__</b></span>
    <span>生成 <b>__GEN__</b></span>
  </div>
</header>

<section class="sec">
  <h2>01 / 主题分布</h2>
  <p class="sub">跨平台去重后，<span class="num">__N__</span> 条收藏落在 <span class="num">__T__</span> 个主题上（一条可命中多主题，故加总大于总数）</p>
  <div class="bars">
      __BARS__
  </div>
</section>

<section class="sec">
  <h2>02 / 跨平台共鸣</h2>
  <p class="sub">同一主题在各平台的出现次数 —— <span class="num">越宽的颜色</span> 代表越"跨平台一致"，即真正的长期注意力所在</p>
  __MATRIX__
</section>

<section class="sec">
  <h2>03 / 收藏总账</h2>
  <p class="sub">全部 <span class="num">__N__</span> 条，可筛选、可搜索、可跳回出处</p>
  <div class="tools">
    <div class="chips" id="plats">
      __PLAT_CHIPS__
    </div>
    <div class="chips" id="themes">
      __THEME_CHIPS__
    </div>
    <div class="row2">
      <input type="search" id="q" placeholder="搜标题 / 作者 / 附注…">
      <select id="sort">
        <option value="default">默认（九平台交错混排）</option>
        <option value="metric">按热度 / 数据</option>
        <option value="platform">按平台聚合</option>
        <option value="theme">按主题聚合</option>
      </select>
      <span class="count" id="cnt"></span>
    </div>
  </div>
  <div class="grid" id="grid"></div>
</section>
__PRIVATE__
<footer>
  数据由 <code>analyze_collections.py</code> 归一化 + 规则式分类（零 token、可复现），页面由 <code>build_collections_board.py</code> 从 <code>data/collect/analysis.json</code> 生成 —— 未手抄任何字段。<br>
  分类为<strong>关键词多标签</strong>，一条内容可命中多个主题；主主题取词表优先序第一个命中项。未归类条目多为 Behance 作品名、纯链接 X 帖与小红书短句，属正常边界。<br>
  隐私隔离依据独立词表（医疗 / 心理 / 性健康），命中即整条排除在统计与建议之外 —— 该词表与选题词表分开维护，避免把私人健康问题误当内容素材。
</footer>
</div>

<script id="DATA" type="application/json">__DATA__</script>
<script>
(function(){
  var D = JSON.parse(document.getElementById('DATA').textContent);
  var items = D.items, TCN = D.themeCn, PAGE = D.pageSize || 48;
  var PC = __PLAT_COLOR__;

  var fP = 'all', fT = 'all', fQ = '', fS = 'default', shown = PAGE, view = [];
  var UNIT = __UNIT__;

  document.getElementById('sTotal').textContent = items.length;
  document.getElementById('sPlat').textContent = new Set(items.map(function(i){return i.p})).size;
  document.getElementById('sTheme').textContent = __T__;
  document.getElementById('sThumb').textContent = items.filter(function(i){return i.th}).length;

  function filter(){
    var q = fQ.trim().toLowerCase();
    view = items.filter(function(i){
      if (fP !== 'all' && i.p !== fP) return false;
      if (fT !== 'all' && i.ts.indexOf(fT) < 0) return false;
      if (q){
        var blob = (i.t + ' ' + i.a + ' ' + i.e + ' ' + i.g + ' ' + i.p).toLowerCase();
        if (blob.indexOf(q) < 0) return false;
      }
      return true;
    });
    if (fS === 'platform'){
      view.sort(function(a,b){ return a.p.localeCompare(b.p) || (b.m||0)-(a.m||0) });
    } else if (fS === 'theme'){
      view.sort(function(a,b){ return a.tp.localeCompare(b.tp) });
    } else if (fS === 'metric'){
      view.sort(function(a,b){ return (parseFloat(String(b.m).replace(/[^0-9.]/g,''))||0) - (parseFloat(String(a.m).replace(/[^0-9.]/g,''))||0) });
    } else {
      // 默认：按平台轮询交错 —— 首屏就有各平台混排 + 尽量先出带图的
      var buckets = {}, porder = [];
      view.forEach(function(i){ if(!buckets[i.p]){ buckets[i.p]=[]; porder.push(i.p);} buckets[i.p].push(i) });
      porder.sort(function(a,b){ return buckets[b].length - buckets[a].length });
      var mixed = [], idx = 0, more = true;
      while (more){
        more = false;
        for (var k = 0; k < porder.length; k++){
          var arr = buckets[porder[k]];
          if (idx < arr.length){ mixed.push(arr[idx]); more = true; }
        }
        idx++;
      }
      view = mixed;
    }
    shown = PAGE;
    render();
  }

  function card(i){
    var color = PC[i.p] || '#888';
    var thumb = i.th
      ? '<a class="thumb" href="'+esc(i.u)+'" target="_blank" rel="noopener noreferrer"><img loading="lazy" src="'+esc(i.th)+'" alt="" referrerpolicy="no-referrer" onerror="this.parentNode.classList.add(\\'no\\')"></a>'
      : '<a class="thumb no" data-p="'+esc(i.p+(i.g?' · '+i.g:''))+' 无预览图" href="'+esc(i.u)+'" target="_blank" rel="noopener noreferrer"></a>';
    var tags = i.ts.slice(0,3).map(function(t){
      return '<span class="tag">'+esc(TCN[t]||t)+'</span>';
    }).join('');
    var title = i.t || i.e || '(无标题)';
    var unit = UNIT[i.p] || '';
    var met = i.m ? '<span class="metric"><em>'+esc(i.m)+'</em>'+(unit?' '+unit:'')+'</span>' : '<span class="metric"></span>';
    return '<article class="card">'+thumb+
      '<div class="body">'+
        '<div class="meta"><span class="badge" style="background:'+color+'">'+esc(i.p)+'</span>'+
          '<span class="grp">'+esc(i.g||'')+'</span></div>'+
        '<p class="tt">'+esc(title)+'</p>'+
        (i.a ? '<div class="au">'+esc(i.a)+'</div>' : '')+
        '<div class="tags">'+tags+'</div>'+
        '<div class="foot">'+met+
          '<a class="go" href="'+esc(i.u)+'" target="_blank" rel="noopener noreferrer">看原帖 ↗</a></div>'+
      '</div></article>';
  }

  function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }

  function render(){
    var g = document.getElementById('grid');
    var slice = view.slice(0, shown);
    var html = slice.map(card).join('');
    if (!view.length) html = '<div class="empty">没有匹配的收藏 —— 换个关键词或点掉筛选试试</div>';
    if (view.length > shown) html += '<div class="more"><button id="loadmore">加载更多（还有 '+(view.length-shown)+' 条）</button></div>';
    g.innerHTML = html;
    document.getElementById('cnt').textContent = view.length + ' / ' + items.length + ' 条';
    var lm = document.getElementById('loadmore');
    if (lm) lm.onclick = function(){ shown += PAGE*2; render(); };
  }

  function chips(boxId, attr){
    document.getElementById(boxId).addEventListener('click', function(e){
      var b = e.target.closest('.chip'); if (!b) return;
      [].forEach.call(this.querySelectorAll('.chip'), function(c){ c.classList.remove('on') });
      b.classList.add('on');
      if (attr === 'p') fP = b.dataset.p; else fT = b.dataset.t;
      filter();
      window.scrollTo({top: document.querySelector('.tools').offsetTop - 8, behavior:'smooth'});
    });
  }
  chips('plats','p'); chips('themes','t');
  document.getElementById('q').addEventListener('input', function(){ fQ = this.value; filter() });
  document.getElementById('sort').addEventListener('change', function(){ fS = this.value; filter() });
  filter();
})();
</script>
</body>
</html>"""

    out = (tpl
           .replace("__N__", str(len(public)))
           .replace("__T__", str(len(themes)))
           .replace("__PV__", str(len(private)))
           .replace("__GEN__", d["generated"].replace("T", " "))
           .replace("__BARS__", theme_bars())
           .replace("__MATRIX__", matrix())
           .replace("__PLAT_CHIPS__", plat_chips())
           .replace("__THEME_CHIPS__", theme_chips())
           .replace("__PRIVATE__", private_block())
           .replace("__PLAT_COLOR__", json.dumps(PLAT_COLOR, ensure_ascii=False))
           .replace("__UNIT__", json.dumps(METRIC_UNIT, ensure_ascii=False))
           .replace("__DATA__", data_json))

    open(out_path, "w", encoding="utf-8").write(out)
    cov_n, cov_need = _sync_covers(out_path, items)
    print("→ %s  (%.0f KB)" % (out_path, len(out.encode("utf-8")) / 1024))
    if cov_need:
        print("   本地封面 %d/%d 张 → %s/covers/" % (cov_n, cov_need,
              os.path.dirname(os.path.abspath(out_path))))
    print("   公开 %d 条 / 隔离 %d 条 / 平台 %d / 主题 %d" % (len(public), len(private), len(plats), len(themes)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=_default_out())
    ap.add_argument("--page", type=int, default=48)
    a = ap.parse_args()
    build(a.out, a.page)
