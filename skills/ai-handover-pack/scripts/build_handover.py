#!/usr/bin/env python3
"""build_handover.py — 把 Obsidian vault 编译成「平台中立」的 AI 交接包。

为什么需要它
------------
vault 里的笔记是给 Obsidian 看的：`[[双链]]`、`![[嵌入]]`、`dataview` 代码块、
frontmatter。这些语法到了扣子 / Kimi / 豆包 / GPTs 那边全是**死字符**——
外部平台读不到链接背后的内容，只看到一堆方括号。

这个脚本做三件事：
  1. 清洗：把 Obsidian 语法展平成纯 Markdown（链接内联成文字，嵌入转成文字说明）
  2. 切分：超过平台单段上限的长文，按 H2 拆成多个文件
  3. 打包：生成 README + zip，直接能上传

两条命令
--------
  clean   单文件转换（快速验证）
      python3 build_handover.py clean 输入.md -o 输出.md

  pack    按 config 出整包
      python3 build_handover.py pack --config pack.json

零第三方依赖。
"""

from __future__ import annotations

import argparse
import os
import json
import re
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

# ── 平台限制（默认按扣子/Coze 官方文档） ───────────────────────────────
MAX_SEGMENT_CHARS = 5000   # 扣子：单个知识库分段最大 5000 字符
MAX_FILES = 300            # 扣子：每个知识库最多 300 个文件

MEDIA_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp",
    ".mp4", ".mov", ".m4v", ".webm",
    ".mp3", ".wav", ".m4a",
    ".psd", ".ai", ".sketch", ".canvas", ".pdf", ".zip",
}

# ── 正则 ──────────────────────────────────────────────────────────────
RE_FRONTMATTER = re.compile(r"\A\ufeff?---\r?\n.*?\r?\n---\r?\n", re.S)
RE_DATAVIEW = re.compile(r"^[ \t]*```(?:dataview|dataviewjs)\b.*?^[ \t]*```[ \t]*$", re.S | re.M)
RE_COMMENT = re.compile(r"%%(?!%)(.*?)%%", re.S)
RE_EMBED = re.compile(r"!\[\[([^\]|#]+)(?:#([^\]|]+))?(?:\|([^\]]*))?\]\]")
RE_WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#([^\]|]+))?(?:\|([^\]]*))?\]\]")
RE_CALLOUT = re.compile(r"^(>[ \t]*)\[!\w+\][-+]?[ \t]*", re.M)
RE_MD_IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
RE_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
RE_TRAILING_WS = re.compile(r"[ \t]+$", re.M)
RE_BLANK_RUN = re.compile(r"\n{4,}")
RE_H2 = re.compile(r"^##[ \t]+\S", re.M)


def strip_frontmatter(text: str) -> tuple[str, dict]:
    """去掉 frontmatter，返回 (正文, 元数据字典)。"""
    m = RE_FRONTMATTER.match(text)
    if not m:
        return text, {}
    raw = m.group(0)
    meta: dict = {}
    for line in raw.splitlines():
        if ":" in line and not line.startswith("---"):
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    body = text[m.end():]
    title = meta.get("title") or meta.get("name")
    if title and not body.lstrip().startswith("#"):
        body = f"# {title.strip().strip(chr(34))}\n\n{body}"
    return body, meta


def inline_link(target: str, anchor: str | None, label: str | None) -> str:
    """把 wiki 链接展平成纯文字。"""
    target = target.strip()
    show = (label or "").strip()
    if show:
        out = show
    else:
        out = Path(target).name
        if out.lower().endswith(".md"):
            out = out[:-3]
    if anchor:
        out = f"{out}（见「{anchor.strip()}」一节）"
    return out


def obsidian_to_plain(text: str) -> str:
    """Obsidian Markdown → 平台中立 Markdown。"""
    text, _ = strip_frontmatter(text)

    # dataview 代码块：对外部平台无意义，整块删掉
    text = RE_DATAVIEW.sub("", text)

    # Obsidian 注释 %%...%% 删掉（保留原有换行数）
    text = RE_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)

    # 嵌入 ![[...]]：媒体实体无法跟着 md 走，转成可读提示
    def _embed(m: re.Match) -> str:
        target, anchor, label = m.group(1), m.group(2), m.group(3)
        name = Path(target.strip()).name
        if Path(name).suffix.lower() in MEDIA_EXT:
            cap = (label or "").strip()
            return f"［素材：{name}{'（' + cap + '）' if cap else ''} —— 二进制文件，未随本包导出］"
        return inline_link(target, anchor, label)

    text = RE_EMBED.sub(_embed, text)

    # 普通链接 [[目标]] / [[目标|显示]] / [[目标#锚点]]
    text = RE_WIKILINK.sub(lambda m: inline_link(m.group(1), m.group(2), m.group(3)), text)

    # Markdown 相对链接/图片：在外部平台是死链，展平
    def _md_target(url: str) -> tuple[str, str] | None:
        """返回 (kind, name)；kind ∈ {'media','doc'}；外链返回 None 表示原样保留。"""
        u = url.strip()
        if u.startswith(("http://", "https://", "mailto:", "#", "data:")):
            return None
        path = u.split("#")[0]
        ext = Path(path).suffix.lower()
        if ext in MEDIA_EXT:
            return ("media", Path(path).name)
        return ("doc", Path(path).name)

    def _as_media(name: str, caption: str) -> str:
        # 说明文字如果就是路径/文件名本身，属于噪音，丢掉
        if caption and (caption == name or caption.endswith(name) or "/" in caption):
            caption = ""
        cap = f"（{caption}）" if caption else ""
        return f"［素材：{name}{cap} —— 二进制文件，未随本包导出］"

    def _md_img(m: re.Match) -> str:
        t = _md_target(m.group(2))
        if t is None:
            return m.group(0)
        return _as_media(t[1], m.group(1).strip())

    def _md_link(m: re.Match) -> str:
        t = _md_target(m.group(2))
        if t is None:
            return m.group(0)
        return m.group(1).strip() if t[0] == "doc" else _as_media(t[1], m.group(1).strip())

    text = RE_MD_IMG.sub(_md_img, text)
    text = RE_MD_LINK.sub(_md_link, text)

    # callout 降级成普通引用
    text = RE_CALLOUT.sub(r"\1", text)

    # 收尾清理
    text = RE_TRAILING_WS.sub("", text)
    text = RE_BLANK_RUN.sub("\n\n\n", text)
    return text.strip() + "\n"


def split_long(text: str, limit: int = MAX_SEGMENT_CHARS - 200) -> list[tuple[str, str]]:
    """超长文档按 H2 切分。返回 [(后缀, 内容), ...]。不超限则返回 [("", text)]。"""
    if len(text) <= limit:
        return [("", text)]

    starts = [m.start() for m in RE_H2.finditer(text)]
    if not starts:
        return [("", text)]  # 没有 H2 可切，原样返回

    blocks: list[tuple[str, str]] = []
    head = text[: starts[0]].strip()
    if head:
        blocks.append(("", head))

    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(text)
        chunk = text[s:e].strip()
        m = re.match(r"^##[ \t]+(.+)", chunk)
        blocks.append(((m.group(1).strip() if m else f"part{i + 1}"), chunk))

    # 合并小段，尽量贴近 limit
    merged: list[tuple[str, str]] = []
    for name, body in blocks:
        if merged and len(merged[-1][1]) + len(body) + 4 <= limit:
            merged[-1] = (merged[-1][0], merged[-1][1] + "\n\n" + body)
        else:
            merged.append((name, body))
    return merged


def slug(name: str, maxlen: int = 28) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", name).strip("-")
    return (s[:maxlen] or "part")


def do_clean(args) -> int:
    src = Path(args.input)
    text = obsidian_to_plain(src.read_text(encoding="utf-8"))
    out = Path(args.output) if args.output else src.with_suffix(".plain.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    warn = ""
    if len(text) > MAX_SEGMENT_CHARS:
        warn = f"  ⚠ {len(text)} 字符 > 单段上限 {MAX_SEGMENT_CHARS}，pack 时会自动按 H2 切分"
    print(f"✓ {src.name} → {out}  ({len(text)} 字符){warn}")
    return 0


def do_pack(args) -> int:
    cfg_path = Path(args.config).resolve()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out_dir = Path(cfg["out"]).expanduser().resolve()
    if out_dir.exists() and not args.force:
        print(f"✗ 输出目录已存在：{out_dir}\n  加 --force 覆盖。", file=sys.stderr)
        return 1
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    written: list[Path] = []
    total_chars = 0

    for doc in cfg["docs"]:
        src = Path(os.path.expandvars(doc["src"])).expanduser()  # 支持 $VAULT_PATH 占位符
        if not src.is_absolute():
            src = (cfg_path.parent / src).resolve()
        if not src.exists():
            print(f"  ⚠ 源文件缺失，跳过：{src}")
            continue

        dest_rel = doc["as"]
        raw = src.read_text(encoding="utf-8")
        if doc.get("clean", True):
            text = obsidian_to_plain(raw)
        else:
            text, _ = strip_frontmatter(raw)
            text = text.rstrip() + "\n"

        parts = split_long(text) if doc.get("split", True) else [("", text)]
        base = Path(dest_rel)

        for suffix, body in parts:
            if suffix:
                name = f"{base.stem} · {slug(suffix)}.md"
            else:
                name = base.name
            dest = out_dir / base.parent / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body, encoding="utf-8")
            written.append(dest)
            total_chars += len(body)

    if len(written) > MAX_FILES:
        print(f"  ⚠ 共 {len(written)} 个文件，超过平台单知识库上限 {MAX_FILES}")

    # README
    readme = render_readme(cfg, out_dir, written, total_chars)
    (out_dir / "README-怎么用.md").write_text(readme, encoding="utf-8")
    written.append(out_dir / "README-怎么用.md")

    # zip
    zip_path = out_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(written):
            z.write(f, f.relative_to(out_dir))

    print(f"✓ 交接包：{out_dir}")
    print(f"  {len(written)} 个文件 · 约 {total_chars:,} 字符")
    print(f"  zip：{zip_path}  ({zip_path.stat().st_size / 1024:.0f} KB)")
    for f in written:
        print(f"    · {f.relative_to(out_dir)}")
    return 0


def render_readme(cfg: dict, out_dir: Path, files: list[Path], chars: int) -> str:
    platform = cfg.get("platform", "外部 AI 平台")
    kb_files = [f for f in files if f.parent.name.startswith("01")]
    others = [f for f in files if f not in kb_files]
    lines = [
        f"# 交接包 · {cfg['pack']}",
        "",
        f"> 目标平台：**{platform}** ｜ 生成日期：{date.today().isoformat()}",
        f"> 内容：{len(files)} 个文件 · 约 {chars:,} 字符",
        "> 由 `ai-handover-pack` 从 Obsidian vault 编译，**平台中立格式**（无双链、无 dataview）。",
        "",
        "---",
        "",
        "## 怎么用（三步）",
        "",
        f"### 1. 粘系统提示词",
        f"把 `00-系统提示词.md` 的**全文**复制进 {platform} 的「人设与回复逻辑」框。",
        "这段决定它是谁、守什么规矩、按什么格式产出。**不要改结构**，要改就改里面的具体条目。",
        "",
        f"### 2. 传知识库",
        f"把 `01-知识库/` 里的 **{len(kb_files)} 个 .md 文件**全部拖进 {platform} 的知识库。",
        "这些文件是它回答的依据——角色长相、语气、生产流程、当前项目状态。",
        "",
        "### 3. 建工作流（可选）",
        "`02-工作流蓝图.md` 是节点图，照着连线即可。不建工作流也能用，只是每次要多说几句。",
        "",
        "---",
        "",
        "## 包内清单",
        "",
        "| 文件 | 用途 |",
        "|------|------|",
    ]
    for f in sorted(files):
        rel = f.relative_to(out_dir)
        desc = cfg.get("descriptions", {}).get(str(rel), "")
        lines.append(f"| `{rel}` | {desc} |")

    lines += [
        "",
        "---",
        "",
        "## 红线（写进提示词了，这里再强调一次）",
        "",
        "- 这个包里**只有设定和生产流程，没有成片素材**。图片/视频实体在 vault 的 `Assets/` 下，",
        "  需要的话单独上传到平台的「图片知识库」。",
        "- 产出物**回流**走 `03-交接回执模板.md`，按那个格式回填，WorkBuddy 才能直接落库。",
        "",
        "## 平台限制速查（扣子/Coze）",
        "",
        "| 项 | 上限 |",
        "|----|------|",
        "| 每个知识库文件数 | 300 |",
        "| 单文件大小 | 100 MB（纯文本 / Markdown **5 MB**） |",
        "| 单段长度 | 5000 字符 |",
        "| 每知识库分段总数 | 10000 |",
        "| 免费版容量 | 1 GB |",
        "",
        "> 本包已按此规格切分，直接上传即可。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Obsidian vault → 平台中立 AI 交接包")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("clean", help="单文件转换")
    c.add_argument("input")
    c.add_argument("-o", "--output")
    c.set_defaults(func=do_clean)

    p = sub.add_parser("pack", help="按 config 出整包")
    p.add_argument("--config", required=True)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=do_pack)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
