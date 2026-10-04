#!/usr/bin/env python3
"""多平台内容调研看板生成器。

用法：
    python3 build_board.py [--keyword 关键词] [--out content-board.html]

输入（存在即加载，缺哪个就跳过哪个）：
    data/board_data.json   B站    [{bvid,title,author,cover,duration,publish,view,like,favorite,reply,url}]
    data/summaries.json    B站官方 AI 总结  {bvid: [{time,content}] | null}
    data/xhs_notes.json    小红书  [{rank,author,title,content,tags,likes,collects,comments,published_at,url}]
    data/dy_notes.json     抖音    [{...}]

设计要点：
- 页面只是「渲染层」，不落地任何媒体文件；封面走远程直链，视频走官方 iframe。
- 数据全部来自 opencli 的结构化 JSON，不经 LLM 二次加工（省 token）。
- 内嵌播放只有 B站/YouTube 行；小红书/抖音/知乎/微博 禁止跨域嵌套，只做卡片+跳转。
- 支持 prefers-color-scheme，浅色/深色都可用。
"""
import argparse, json, os, re
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def load(name):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def normalise():
    items = []
    bili = load("board_data.json") or []
    summ = load("summaries.json") or {}
    for i, b in enumerate(bili):
        items.append({
            "platform": "bilibili",
            "id": b.get("bvid", ""),
            "rank": b.get("rank", i + 1),
            "title": b.get("title", ""),
            "author": b.get("author", ""),
            "cover": re.sub(r"^http://", "https://", b.get("cover", "") or ""),
            "duration": b.get("duration", ""),
            "date": b.get("publish", ""),
            "url": b.get("url", ""),
            "m1": b.get("view", ""), "m2": b.get("like", ""),
            "m3": b.get("favorite", ""), "m4": b.get("reply", ""),
            "summary": summ.get(b.get("bvid", "")),
        })
    for i, x in enumerate(load("xhs_notes.json") or []):
        items.append({
            "platform": "xiaohongshu",
            "id": str(x.get("rank", i + 1)),
            "rank": x.get("rank", i + 1),
            "title": x.get("title", ""),
            "author": x.get("author", ""),
            "cover": "",
            "content": x.get("content", ""),
            "tags": x.get("tags", ""),
            "date": x.get("published_at", ""),
            "url": x.get("url", ""),
            "m1": x.get("likes", ""), "m2": x.get("collects", ""),
            "m3": x.get("comments", ""), "m4": "",
        })
    for i, d in enumerate(load("dy_notes.json") or []):
        items.append({
            "platform": "douyin",
            "id": str(i + 1), "rank": d.get("rank", i + 1),
            "title": d.get("title", ""), "author": d.get("author", ""),
            "cover": re.sub(r"^http://", "https://", d.get("cover", "") or ""),
            "content": d.get("content", ""), "tags": d.get("tags", ""),
            "date": d.get("published_at", ""), "url": d.get("url", ""),
            "m1": d.get("likes", ""), "m2": d.get("comments", ""),
            "m3": d.get("shares", ""), "m4": "",
        })
    return items


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>内容调研看板 · __KEYWORD__</title>
<style>
  :root{
    --bg:#F7F7F5; --card:#FFF; --line:#E5E4E0; --line2:#EFEEEA;
    --tx:#1F1F1D; --tx2:#6B6B66; --tx3:#9A9A94;
    --accent:#185FA5; --accentbg:#F4F9FD; --accentbd:#BFD9F0;
    --bili:#FB7299; --xhs:#FF2E4D; --dy:#111;
    --chipbg:#FFF; --media:#EDECE8; --hover:#CFCEC9;
  }
  @media (prefers-color-scheme: dark){
    :root{
      --bg:#141414; --card:#1E1E1E; --line:#2E2E2E; --line2:#282828;
      --tx:#EDEDEA; --tx2:#9E9E98; --tx3:#6E6E68;
      --accent:#7FB4E0; --accentbg:#16232E; --accentbd:#2C4A63;
      --xhs:#FF6B7E; --chipbg:#1E1E1E; --media:#242424; --hover:#3A3A3A;
      --bili:#FB7299; --dy:#DDD;
    }
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--tx);
       font:14px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;}
  .wrap{max-width:1240px;margin:0 auto;padding:28px 24px 64px}

  header{border-bottom:1px solid var(--line);padding-bottom:18px;margin-bottom:18px}
  h1{margin:0 0 6px;font-size:20px;font-weight:600;letter-spacing:.2px}
  .sub{color:var(--tx2);font-size:13px}
  .sub code{background:var(--card);border:1px solid var(--line);border-radius:5px;padding:1px 6px;
            font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:var(--tx)}

  .bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:16px 0 20px}
  .chips{display:flex;gap:8px;flex-wrap:wrap}
  .chip{border:1px solid var(--line);background:var(--chipbg);border-radius:999px;
        padding:5px 13px;font-size:13px;color:var(--tx2);cursor:pointer;user-select:none;
        display:flex;align-items:center;gap:7px;font-family:inherit}
  .chip.on{border-color:var(--tx);color:var(--tx);font-weight:500}
  .chip .dot{width:7px;height:7px;border-radius:50%;background:var(--tx3)}
  .chip[data-p=bilibili].on .dot{background:var(--bili)}
  .chip[data-p=xiaohongshu].on .dot{background:var(--xhs)}
  .chip[data-p=douyin].on .dot{background:var(--dy)}
  .chip .n{font-size:11px;color:var(--tx3)}
  .chip.disabled{opacity:.5;cursor:not-allowed}
  .spacer{flex:1}
  input[type=search],select{border:1px solid var(--line);background:var(--chipbg);border-radius:8px;
        padding:7px 12px;font-size:13px;color:var(--tx);outline:none;font-family:inherit}
  input[type=search]{min-width:180px}
  input[type=search]:focus{border-color:var(--hover)}

  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;
        display:flex;flex-direction:column;transition:border-color .14s}
  .card:hover{border-color:var(--hover)}

  .media{position:relative;aspect-ratio:16/9;background:var(--media);overflow:hidden}
  .media img{width:100%;height:100%;object-fit:cover;display:block}
  .media iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
  .nocover{width:100%;height:100%;display:flex;align-items:center;justify-content:center;
        background:var(--media);color:var(--tx3);font-size:12px}
  .dur{position:absolute;right:8px;bottom:8px;background:rgba(0,0,0,.72);color:#fff;
       font-size:11px;padding:2px 6px;border-radius:4px;font-variant-numeric:tabular-nums}
  .play{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
        background:rgba(0,0,0,.16);opacity:0;transition:opacity .15s;cursor:pointer;border:0;width:100%}
  .media:hover .play{opacity:1}
  .play span{width:46px;height:46px;border-radius:50%;background:rgba(255,255,255,.94);
        display:flex;align-items:center;justify-content:center}
  .play svg{width:17px;height:17px;fill:#1F1F1D;margin-left:2px}

  .body{padding:13px 15px 15px;display:flex;flex-direction:column;gap:9px;flex:1}
  .badge{display:inline-flex;align-items:center;gap:6px;font-size:11px;color:var(--tx3);font-weight:500}
  .badge .b{width:6px;height:6px;border-radius:50%}
  .badge.p-bilibili .b{background:var(--bili)}
  .badge.p-xiaohongshu .b{background:var(--xhs)}
  .badge.p-douyin .b{background:var(--dy)}
  .t{font-size:14.5px;font-weight:500;line-height:1.45;color:var(--tx);
     display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
  .c{font-size:12.5px;color:var(--tx2);line-height:1.65;
     display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;white-space:pre-wrap}
  .tags{display:flex;flex-wrap:wrap;gap:5px}
  .tag{font-size:11px;color:var(--tx2);background:var(--line2);border-radius:5px;padding:2px 7px}
  .who{font-size:12.5px;color:var(--tx2);display:flex;align-items:center;gap:6px}
  .who .av{width:17px;height:17px;border-radius:50%;opacity:.85;flex:none;
     display:flex;align-items:center;justify-content:center;color:#fff;font-size:9px}
  .av.p-bilibili{background:var(--bili)} .av.p-xiaohongshu{background:var(--xhs)} .av.p-douyin{background:var(--dy)}
  .stats{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--tx2);
         padding-top:9px;border-top:1px solid var(--line2);font-variant-numeric:tabular-nums}
  .stats b{font-weight:500;color:var(--tx)}
  .stats i{font-style:normal;color:var(--tx3);margin-right:3px}
  .meta{font-size:11.5px;color:var(--tx3)}
  .act{display:flex;gap:8px;margin-top:2px}
  .act a,.act button{flex:1;text-align:center;text-decoration:none;font-size:12.5px;
        padding:7px 0;border-radius:7px;border:1px solid var(--line);background:var(--card);
        color:var(--tx2);cursor:pointer;font-family:inherit;transition:border-color .12s,color .12s}
  .act a:hover,.act button:hover{border-color:var(--hover);color:var(--tx)}
  .act .primary{border-color:var(--accentbd);color:var(--accent);background:var(--accentbg)}
  .act .primary:hover{border-color:var(--accent)}
  .sum{margin-top:2px;border-top:1px dashed var(--line);padding-top:9px;display:none}
  .sum.open{display:block}
  .sum .seg{display:flex;gap:9px;font-size:12px;color:var(--tx2);line-height:1.6;padding:3px 0}
  .sum .seg time{flex:none;color:var(--tx3);font-variant-numeric:tabular-nums;min-width:40px}

  .empty{grid-column:1/-1;text-align:center;color:var(--tx3);padding:56px 0;font-size:13px}
  footer{margin-top:34px;padding-top:16px;border-top:1px solid var(--line);
         font-size:12px;color:var(--tx3);line-height:1.9}
  footer code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;
     background:var(--card);border:1px solid var(--line);border-radius:4px;padding:1px 5px;color:var(--tx2)}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>内容调研看板 · <span id="kw">__KEYWORD__</span></h1>
    <div class="sub">
      抓取 __BUILT__ · 共 <b>__COUNT__</b> 条 ·
      零下载、零 token（结构化 JSON 直读，不喂 HTML）
    </div>
  </header>

  <div class="bar">
    <div class="chips" id="chips"></div>
    <div class="spacer"></div>
    <input type="search" id="q" placeholder="筛选标题 / 作者 / 正文…">
    <select id="sort">
      <option value="rank">按搜索排名</option>
      <option value="m1">按主指标</option>
      <option value="new">按发布时间</option>
    </select>
  </div>

  <div class="grid" id="grid"></div>

  <footer>
    抓取链路（可复现）：<br>
    · B站：<code>opencli bilibili search "K" -f json</code> → <code>bilibili video &lt;BV&gt; -f json</code>；官方 AI 总结 <code>bilibili summary &lt;BV&gt;</code>（逐视频有效，本次实测 1/6）；字幕 <code>bilibili subtitle</code>（本次实测 3/6）<br>
    · 小红书：<code>opencli xiaohongshu search "K" -f json</code> → <code>xiaohongshu note &lt;完整URL&gt; -f json</code>（必须传完整 URL，只传 ID 会空返回）<br>
    · 抖音：<code>opencli douyin search "K" -f json</code> —— v1.8.6 适配器有 bug（MutationObserver 报错），当前不可用<br>
    本页仅渲染：封面走远程直链，视频走 B站官方播放器 iframe —— 全程不落地任何文件。<br>
    内嵌播放仅 B站/YouTube 支持；小红书/抖音/知乎/微博 禁止跨域嵌套，只能卡片 + 跳转。
  </footer>
</div>

<script>
const DATA = __DATA__;
const META = {
  bilibili:    {label:'B站',    uni:['播放','点赞','收藏','评论']},
  xiaohongshu: {label:'小红书', uni:['点赞','收藏','评论','']},
  douyin:      {label:'抖音',   uni:['点赞','评论','分享','']}
};
const $ = s => document.querySelector(s);
const nf = v => { if (v === '' || v == null) return '—';
  if (typeof v === 'string' && /[万wW]/.test(v)) return v;
  const n = +v; if (!n) return '—';
  return n >= 10000 ? (n/10000).toFixed(1)+'万' : n.toLocaleString(); };
function dur(s){ const m = /\((\d+)s\)/.exec(s || ''); if (!m) return s || '';
  const t = +m[1], h = (t/3600)|0, mi = ((t%3600)/60)|0, se = t%60;
  return (h ? h+':'+String(mi).padStart(2,'0') : mi) + ':' + String(se).padStart(2,'0'); }
const esc = s => String(s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function card(it){
  const meta = META[it.platform] || META.bilibili;
  const el = document.createElement('div'); el.className = 'card';

  let media = '';
  if (it.platform === 'bilibili' || it.cover){
    const cover = it.cover
      ? '<img src="'+esc(it.cover)+'" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.replaceWith(Object.assign(document.createElement(\'div\'),{className:\'nocover\',textContent:\'封面加载失败\'}))">'
      : '<div class="nocover">无封面</div>';
    media = '<div class="media">'+cover+
      (it.duration ? '<div class="dur">'+dur(it.duration)+'</div>' : '')+
      (it.platform === 'bilibili' ? '<button class="play" title="内嵌播放"><span><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></span></button>' : '')+
      '</div>';
  }

  const tagList = (it.tags || '').split(',').map(t => t.trim()).filter(Boolean).slice(0, 6);
  const stats = meta.uni.map((u, i) => {
    const v = it['m' + (i+1)];
    return (u && v !== '' && v != null) ? '<span><i>'+u+'</i><b>'+nf(v)+'</b></span>' : '';
  }).join('');

  const hasSum = Array.isArray(it.summary) && it.summary.length;
  const sumHtml = hasSum ? '<div class="sum" id="sum-'+esc(it.id)+'">' + it.summary.map(s =>
      '<div class="seg"><time>'+esc(s.time||'')+'</time><span>'+esc(s.content).replace(/^#\s*/,'')+'</span></div>').join('') + '</div>' : '';

  el.innerHTML =
    media +
    '<div class="body">'+
      '<div class="badge p-'+it.platform+'"><span class="b"></span>'+meta.label+' · 排名 #'+it.rank+'</div>'+
      '<div class="t">'+esc(it.title)+'</div>'+
      (it.content ? '<div class="c">'+esc(it.content)+'</div>' : '')+
      (tagList.length ? '<div class="tags">'+tagList.map(t=>'<span class="tag">'+esc(t)+'</span>').join('')+'</div>' : '')+
      '<div class="who"><span class="av p-'+it.platform+'">'+meta.label[0]+'</span><span>'+esc(it.author)+'</span></div>'+
      '<div class="stats">'+stats+'</div>'+
      (it.date ? '<div class="meta">'+esc(it.date)+'</div>' : '')+
      sumHtml +
      '<div class="act">'+
        (hasSum ? '<button class="primary" data-sum="sum-'+esc(it.id)+'">AI 总结</button>' : '')+
        (it.platform === 'bilibili' ? '<button class="primary" data-play="1">内嵌播放</button>' : '')+
        '<a href="'+esc(it.url)+'" target="_blank" rel="noopener">打开原页</a>'+
      '</div>'+
    '</div>';

  const box = el.querySelector('.media');
  if (box){
    const play = () => {
      if (box.querySelector('iframe')) return;
      box.style.background = '#000';
      box.innerHTML = '<iframe src="//player.bilibili.com/player.html?bvid='+esc(it.id)+
        '&autoplay=1&danmaku=0&high_quality=1" allowfullscreen scrolling="no" frameborder="0"></iframe>';
    };
    const pb = el.querySelector('.play'); if (pb) pb.onclick = play;
    const bp = el.querySelector('[data-play]'); if (bp) bp.onclick = play;
  }
  const sb = el.querySelector('[data-sum]');
  if (sb) sb.onclick = () => { const s = document.getElementById(sb.dataset.sum);
    s.classList.toggle('open');
    sb.textContent = s.classList.contains('open') ? '收起总结' : 'AI 总结'; };
  return el;
}

const active = new Set(Object.keys(META));
function buildChips(){
  const count = {}; DATA.forEach(d => count[d.platform] = (count[d.platform]||0)+1);
  const c = $('#chips'); c.innerHTML = '';
  Object.keys(META).forEach(p => {
    const n = count[p] || 0;
    const d = document.createElement('div');
    d.className = 'chip' + (active.has(p) ? ' on' : '') + (n ? '' : ' disabled');
    d.dataset.p = p;
    d.innerHTML = '<span class="dot"></span>'+META[p].label+' <span class="n">'+(n||'不可用')+'</span>';
    d.onclick = () => { if (!n) return; active.has(p) ? active.delete(p) : active.add(p); buildChips(); render(); };
    c.appendChild(d);
  });
}

function render(){
  const q = ($('#q').value || '').trim().toLowerCase();
  const sort = $('#sort').value;
  let rows = DATA.filter(d => active.has(d.platform))
                 .filter(d => !q || ((d.title||'')+(d.author||'')+(d.content||'')+(d.tags||'')).toLowerCase().includes(q));
  const parse = v => { if (typeof v === 'string' && /万/.test(v)) return parseFloat(v)*10000; return +v||0; };
  rows.sort((a,b) => sort === 'new' ? String(b.date||'').localeCompare(String(a.date||''))
                                    : sort === 'm1' ? parse(b.m1) - parse(a.m1)
                                    : a.rank - b.rank);
  const g = $('#grid'); g.innerHTML = '';
  if (!rows.length){ g.innerHTML = '<div class="empty">没有匹配的内容</div>'; return; }
  rows.forEach(r => g.appendChild(card(r)));
}
$('#q').oninput = render;
$('#sort').onchange = render;
buildChips(); render();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyword", default=os.environ.get("BOARD_KEYWORD", "AI短剧"))
    ap.add_argument("--out", default=os.path.join(HERE, "content-board.html"))
    a = ap.parse_args()

    items = normalise()
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(items, ensure_ascii=False, indent=1))
            .replace("__KEYWORD__", esc(a.keyword))
            .replace("__COUNT__", str(len(items)))
            .replace("__BUILT__", datetime.now().strftime("%Y-%m-%d %H:%M")))
    open(a.out, "w", encoding="utf-8").write(html)
    by = {}
    for i in items:
        by[i["platform"]] = by.get(i["platform"], 0) + 1
    print("wrote %s | %d items %s | %d bytes" % (a.out, len(items), by, len(html)))


if __name__ == "__main__":
    main()
