#!/usr/bin/env python3
"""跨平台收藏总账 —— 统一 + 分类。

归一化 7 平台（新拉）+ vault 历史数据集 → 关键词多标签分类 → 输出统计。
规则式（可复现、零 token、可审计），不调 LLM。

用法： python3 analyze_collections.py
输出： data/collect/analysis.json
"""
import json, os, hashlib
from collections import Counter, defaultdict
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))


def _find_coll():
    """数据目录自适应 —— 同一份脚本在 WorkBuddy 工作区与 vault 003-Workbench/_build/ 都能跑。"""
    cands = [
        os.path.join(HERE, "data", "collect"),                    # 与脚本同级的自包含副本
        os.path.join(HERE, "..", "data", "collect"),              # vault: 003-Workbench/_build/ → ../data/
        os.path.join(HERE, "..", "collections-ledger", "data", "collect"),
        os.path.join(os.getcwd(), "data", "collect"),
    ]
    for c in cands:
        if os.path.isdir(c):
            return os.path.abspath(c)
    return os.path.abspath(cands[0])


def _find_vault_data():
    cands = [
        "~/Documents/hermes_vault_clean/003-Workbench/data",
        os.path.join(HERE, "..", "data"),
        os.path.join(HERE, "..", "..", "003-Workbench", "data"),
    ]
    for c in cands:
        if os.path.isdir(c):
            return os.path.abspath(c)
    return cands[0]


COLL = _find_coll()
VAULT = _find_vault_data()


# ---------- 主题分类表（顺序 = 优先级，取第一个命中作主主题） ----------
TAXONOMY = [
    ("ai-video", "AI 视频与生成", [
        "ai视频", "ai短剧", "ai漫剧", "生成视频", "文生视频", "图生视频", "seedance", "veo",
        "sora", "runway", "kling", "可灵", "即梦", "jimeng", "midjourney", "higgsfield",
        "提示词", "prompt", "故事板", "分镜", "tvc", "aigc", "omni", "libtv", "tapnow",
        "ai 做", "用ai", "ai创作", "ai绘图", "视频模型", "ai film", "ai filmmaker",
        "ai 视频", "视频生成", "imagegen", "nano banana", "gemini", "veo3"]),
    ("audio-sfx", "音频 · 音效 · 配音", [
        "音效", "广播剧", "配音", "bgm", "音频", "录音", "响度", "声音", "sound",
        "music", "音乐", "voice", "voc", "混音", "配乐", "asmr"]),
    ("3d-motion", "3D · 动态设计", [
        "blender", "3d", "建模", "渲染", "rig", "motion", "动态设计", "摄像机", "镜头运动",
        "材质", "maya", "c4d", "houdini", "unreal", "ue5", "特效", "vfx", "动画", "骨架",
        "stop motion", "定格", "微缩", "产品动画", "animation", "portfolio", "showreel",
        "character animation", "lookdev"]),
    ("craft-film", "影视 · 编导 · 叙事", [
        "编导", "导演", "艺考", "影评", "电影", "纪录片", "剧本", "叙事", "剧集", "单元剧",
        "短片", "netflix", "剧中", "拍了", "cinemat", "filmmak", "commercial", "tvc"]) ,
    ("tool-workflow", "工具 · 工作流 · 自动化", [
        "skill", "工作流", "workflow", "自动化", "notion", "obsidian", "插件", "快捷键",
        "excel", "模板", "版式", "画册", "工具", "app", "软件", "脚本", "自部署", "api",
        "开源", "github", "claude", "代码", "编程", "vibe coding", "comfy", "node",
        "agent", "mcp", "自建", "服务器", "nas", "docker", "省钱", "订阅",
        # 下载器 / 扩展 / 爬虫（GitHub Star 高频）
        "downloader", "ripper", "extension", "chrome-extension", "tampermonkey",
        "scraper", "crawler", "bot", "cli", "sync", "backup", "self-host", "homelab",
        "vpn", "proxy", "订阅转换", "去广告", "自动化脚本", "prompt engineering"]),
    ("career-money", "职业 · 变现 · 转型", [
        "招聘", "offer", "求职", "简历", "管培生", "副业", "不上班", "赚钱", "变现", "接单",
        "自由职业", "转型", "行业", "面试", "外包", "甲方", "商务", "定价", "报价", "创业",
        "生意", "客户", "职业", "工作", "裁员", "gap", "裸辞", "打工"]),
    ("teaching-en", "教学 · 英语 · 资质", [
        "tkt", "剑桥", "英语", "雅思", "教师", "教学", "老师", "tefl", "celta", "native",
        "english", "language", "移民英语"]),
    ("identity-move", "海外 · 回国 · 身份", [
        "回国", "留学", "中留服", "认证", "出国", "护照", "移民", "签证", "海外", "欧洲",
        "亚洲男人", "国外", "异国", "abc", "文化差异", "中西方", "kiwi", "nz", "新西兰"]),
    ("culture-genz", "文化观察 · 社会", [
        "gen z", "表演性", "performative", "renaissance", "optimism", "文化", "社会", "实验",
        "陌生人", "身份", "阶级", "寒门", "底层", "阶层", "community", "社群",
        "internet culture", "algorithm", "viral", "attention", "spectacle", "authenticity",
        "consumerism", "capitalism", "modern life", "loneliness epidemic"]),
    ("growth-mind", "自我成长 · 心理 · 关系", [
        "内耗", "焦虑", "情绪", "自救", "治愈", "shadow", "jung", "自律", "习惯", "关系",
        "恋爱", "分手", "讨好", "表达欲", "自我", "迷茫", "成长", "自尊", "心理", "冥想",
        "focus", "charisma", "激励", "鸡汤", "躺平", "幸福", "创作欲", "拖延", "能量",
        "burnout", "impostor", "confidence", "discipline", "therapy", "healing", "journaling",
        "mindset", "loneliness", "belonging", "storytelling", "personal growth"]),
    ("aesthetic-ref", "审美 · 视觉参考", [
        "审美", "胶片", "版式", "颜色", "视觉", "摄影", "plog", "排版", "海报", "字体",
        "配色", "参考", "design", "aesthetic", "风格", "构图", "moodboard", "typograph",
        "brand", "品牌", "graphic", "illustration", "插画",
        # Behance 设计领域词
        "advertising", "photography", "ui/ux", "fine arts", "fashion", "packaging",
        "editorial", "print", "art direction", "character design", "digital art",
        "product design", "architecture", "interaction design", "drawing", "painting",
        "craft", "sculpt", "poster", "logo", "identity", "visual identity", "cover",
        # Pinterest 视觉参考库高频（board 名 + Pinterest 自动 alt 文本）
        "photo reference", "photography", "photograph", "portrait", "album art",
        "album cover", "indoor photography", "lighting", "color grade", "composition",
        "staged", "set design", "mood", "reference", "outfit", "style"]),
    ("health-body", "身体 · 健康 · 外貌", [
        "健康", "治疗", "痊愈", "病", "医生", "药", "锻炼", "健身", "减肥", "睡眠", "外貌",
        "穿搭", "护肤", "形象", "皮肤", "医美"]),
    ("creative-life", "创作 · 表达 · 灵感", [
        "创作", "灵感", "同类", "表达", "作品", "艺术", "手作", "匠", "审美积累", "日记",
        "drawing", "creative", "artist", "inspiration", "craft", "studio", "做东西"]),
]

# ⚠️ 隐私桶：命中即整个条目标记 private，不进「创作机会」段。
# 与 TAXONOMY 分开维护 —— 因为这类词（医疗/性健康）绝不能被当成选题素材。
PRIVATE_KW = [
    "尖锐湿疣", "hpv", "性病", "梅毒", "艾滋", "hiv", "疱疹", "尿道", "龟头", "生殖器",
    "肛", "妇炎", "霉菌", "滴虫", "衣原体", "支原体", "前列腺", "早泄", "阳痿", "勃起",
    "性功能", "性欲", "性伴侣", "不洁性", "检测阳性", "化验单", "复查阴性", "传染",
    "抑郁症", "焦虑症", "双相", "精神科", "心理咨询", "自残", "轻生", "自杀", "躯体化",
    "长期服药", "慢性病", "癌", "肿瘤", "手术", "住院", "病例", "诊断书",
]


def is_private(text):
    t = (text or "").lower()
    return any(w in t for w in PRIVATE_KW)

THEME_CN = {k: cn for k, cn, _ in TAXONOMY}
THEME_CN["other"] = "其它 / 未归类"


def classify(text):
    t = (text or "").lower()
    hits = [k for k, _, kws in TAXONOMY if any(w.lower() in t for w in kws)]
    return hits or ["other"]


def jload(p, default=None):
    try:
        if p.endswith(".jsonl"):
            return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
        return json.load(open(p, encoding="utf-8"))
    except Exception as e:
        print("  ! 读取失败 %s: %s" % (os.path.basename(p), e))
        return default


ITEMS = []


def add(rows, platform, group, tf, af=None, uf="url", mf=None, df=None, ef=None, private=False, thumbf=None):
    """rows: list[dict]；tf/af/uf/mf/df/ef = 标题/作者/链接/指标/日期/附注 的字段名（或 list 拼接）。
    thumbf: 缩略图字段名（可为 list，取第一个非空的）。"""
    n = 0
    for r in rows or []:
        if not isinstance(r, dict):
            continue

        def g(f):
            if not f:
                return ""
            if isinstance(f, (list, tuple)):
                out = []
                for x in f:
                    v = r.get(x)
                    if isinstance(v, (list, tuple)):      # 如 Behance fields / GH topics
                        out += [str(y) for y in v if y]
                    elif v:
                        out.append(str(v))
                return " · ".join(out).strip()
            v = r.get(f)
            if isinstance(v, (list, tuple)):
                return " · ".join(str(y) for y in v if y)
            return str(v or "").strip()

        thumb = ""
        if thumbf:
            for f in (thumbf if isinstance(thumbf, (list, tuple)) else [thumbf]):
                v = r.get(f)
                if isinstance(v, (list, tuple)) and v:
                    v = v[0]
                if v:
                    thumb = str(v)
                    break

        ITEMS.append({
            "platform": platform, "group": group,
            "title": g(tf), "author": g(af), "url": g(uf),
            "metric": g(mf), "date": g(df), "extra": g(ef),
            "thumb": thumb,
            "private": bool(private),
        })
        n += 1
    print("  + %-10s %-8s %3d" % (platform, group, n))


print("== 装载 ==")
# ---- 本次新拉（7 平台）----
add(jload(f"{COLL}/bili_favorite.json"), "B站", "收藏夹", "title", "author", "url", "plays")
add(jload(f"{COLL}/xhs_saved.json"), "小红书", "收藏", "title", "author", "url", "likes")
add(jload(f"{COLL}/xhs_liked.json"), "小红书", "赞过", "title", "author", "url", "likes")
add(jload(f"{COLL}/yt_watchlater.json"), "YouTube", "稍后再看", "title", "channel", "url", "views", "published")
add(jload(f"{COLL}/weibo_favorites.json"), "微博", "收藏", "text", "author", "url", "likes")
add(jload(f"{COLL}/zhihu_items.json"), "知乎", "收藏夹", "title", "author", "url", "votes", None, "collection")
add(jload(f"{COLL}/pinterest_pins.json", default=[]), "Pinterest", "Pin", ["title", "desc", "alt"], "board", "url", "saves", "created", ["board", "domain"], thumbf="img")

# ---- vault 历史 ----
add(jload(f"{VAULT}/xbookmarks-bookmarks-2026-09-21.json"), "X", "收藏", "text", "name", "url", "likes", "created_at", None, thumbf="media_posters")
add(jload(f"{VAULT}/xbookmarks-likes-2026-09-20.json"), "X", "赞过", "text", "name", "url", "likes", "created_at", None, thumbf="media_posters")
add(jload(f"{VAULT}/xbookmarks-articles-2026-09-20.json"), "X", "长文", "title", "author", "url", "likes", None,
    ["content"])          # 长文正文参与分类（截断）
add(jload(f"{VAULT}/gh-stars-2026-09-21.jsonl"), "GitHub", "Star", "full_name", None, "url",
    "stars", "starred_at", ["description", "topics", "language"])
_bh = jload(f"{VAULT}/behance-pool.json", default={})
_bh_items = _bh.get("items") if isinstance(_bh, dict) else _bh
add(_bh_items, "Behance", "池", "title", "author", "url", "view", "publish", ["fields", "source"], thumbf="cover")

# 缩略图派生：YouTube 由视频 id 拼、GitHub 用官方 og 卡片
import re as _re
for it in ITEMS:
    if not it.get("thumb"):
        if it["platform"] == "YouTube":
            m = _re.search(r"[?&]v=([\w-]{6,})", it["url"] or "")
            if m:
                it["thumb"] = "https://i.ytimg.com/vi/%s/mqdefault.jpg" % m.group(1)
        elif it["platform"] == "GitHub" and it["title"]:
            it["thumb"] = "https://opengraph.githubassets.com/1/%s" % it["title"]

# 小红书封面：fetch_covers.py 用原生 download 命令已落盘到 covers/<note_id>.jpg
# 看板以**相对路径**引用（file:// 直接双击也能显示），不依赖图床、不依赖登录态。
_xc = jload(f"{COLL}/xhs_covers_local.json", default={}) or {}
_xc_hit = 0
for it in ITEMS:
    if it["platform"] == "小红书" and not it.get("thumb"):
        ids = _re.findall(r"[0-9a-f]{24}", it["url"] or "")
        if ids and _xc.get(ids[-1]):
            it["thumb"] = _xc[ids[-1]]
            _xc_hit += 1
print("  ~ 小红书封面命中 %d 张（映射表 %d 条）" % (_xc_hit, len(_xc)))

# 长文正文截断，避免分类被全文淹没（取前 400 字）
for it in ITEMS:
    if it["platform"] == "X" and it["group"] == "长文" and len(it["extra"]) > 400:
        it["extra"] = it["extra"][:400]

# ---- 去重（同 URL 只留一条）----
seen, dedup = set(), []
for it in ITEMS:
    key = hashlib.md5((it["url"] or it["title"]).encode("utf-8", "ignore")).hexdigest()
    if key in seen:
        continue
    seen.add(key)
    dedup.append(it)

# ---- 分类 ----
for it in dedup:
    blob = " ".join([it["title"], it["author"], it["extra"], it["group"]])
    it["themes"] = classify(blob)
    if is_private(blob):                       # 医疗/心理隐私 → 强制入隐私桶
        it["private"] = True
        it["themes"] = ["health-body"] + [t for t in it["themes"] if t != "health-body"]
    it["theme_primary"] = it["themes"][0]

# ---- 统计 ----
by_platform = Counter(i["platform"] for i in dedup)
theme_total = Counter()
theme_by_plat = defaultdict(Counter)
theme_primary_total = Counter(i["theme_primary"] for i in dedup)
for i in dedup:
    for t in i["themes"]:
        theme_total[t] += 1
        theme_by_plat[t][i["platform"]] += 1

PRIVATE_THEMES = {"health-body"}

out = {
    "generated": datetime.now().isoformat(timespec="seconds"),
    "total": len(dedup),
    "private_count": sum(1 for i in dedup if i["private"]),
    "by_platform": dict(by_platform.most_common()),
    "by_platform_group": dict(Counter(f'{i["platform"]}·{i["group"]}' for i in dedup).most_common()),
    "theme_total": dict(theme_total.most_common()),
    "theme_primary_total": dict(theme_primary_total.most_common()),
    "theme_by_platform": {t: dict(c.most_common()) for t, c in theme_by_plat.items()},
    "theme_cn": THEME_CN,
    "private_themes": sorted(PRIVATE_THEMES),
    "items": dedup,
}
json.dump(out, open(f"{COLL}/analysis.json", "w"), ensure_ascii=False, indent=1)

# ---- 打印 ----
print("\n== 总计 %d 条（去重后）==" % len(dedup))
print("   其中隐私桶（医疗/心理，不进选题建议）: %d 条" % sum(1 for i in dedup if i["private"]))
print("\n== 按平台 ==")
for p, n in by_platform.most_common():
    print("  %-10s %4d" % (p, n))
print("\n== 主题分布（多标签计数 / 主主题计数）==")
for t, n in theme_total.most_common():
    mark = "  ⚠️隐私" if t in PRIVATE_THEMES else ""
    print("  %-18s %4d  (主 %d)%s" % (THEME_CN.get(t, t), n, theme_primary_total[t], mark))
print("\n== 主题 × 平台（前 10 主题）==")
for t, _ in theme_total.most_common(10):
    row = " ".join("%s:%d" % (p, c) for p, c in theme_by_plat[t].most_common(8))
    print("  %-18s %s" % (THEME_CN.get(t, t), row))
print("\n== 跨平台共鸣主题（出现在 ≥3 个平台）==")
for t, c in sorted(theme_by_plat.items(), key=lambda x: -len(x[1])):
    if len(c) >= 3:
        print("  %-18s 覆盖 %d 平台: %s" % (THEME_CN.get(t, t), len(c), ", ".join(c.keys())))
print("\n→ 写入 data/collect/analysis.json")
