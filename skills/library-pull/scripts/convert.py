#!/usr/bin/env python3
"""把资料库 doc 的组件语法还原成 Markdown。"""
import os
import re
import textwrap

RAW = os.environ.get("CONVERT_SRC", "raw")
OUT = os.environ.get("CONVERT_OUT", "md")

TAG_RE = re.compile(r'<(/?)([A-Za-z][A-Za-z0-9]*)((?:"[^"]*"|[^>"])*?)(/?)>', re.S)


def strip_wrapper(text):
    text = re.sub(r'\nKS_DOC_REVIEWS\t[^\n]*\n?$', '\n', text)
    text = re.sub(r'^---\ntitle:.*?\n---\n', '', text, flags=re.S)
    return text


def parse(text):
    root = {"tag": None, "attrs": "", "children": []}
    stack = [root]
    pos = 0
    for m in TAG_RE.finditer(text):
        seg = text[pos:m.start()]
        if seg:
            stack[-1]["children"].append({"text": seg})
        closing, tag, attrs, selfclose = m.group(1), m.group(2), m.group(3), m.group(4)
        if closing:
            if len(stack) > 1:
                stack.pop()
        elif selfclose:
            stack[-1]["children"].append({"tag": tag, "attrs": attrs, "children": []})
        else:
            node = {"tag": tag, "attrs": attrs, "children": []}
            stack[-1]["children"].append(node)
            stack.append(node)
        pos = m.end()
    if pos < len(text):
        stack[-1]["children"].append({"text": text[pos:]})
    return root


def attr(node, name, default=None):
    m = re.search(rf'{name}="([^"]*)"', node.get("attrs") or "")
    return m.group(1) if m else default


def inline(node):
    parts = []
    for c in node["children"]:
        if "text" in c:
            parts.append(c["text"])
        elif c["tag"] == "Mark":
            body = inline(c)
            style = (c["attrs"] or "").strip()
            if "italic" in style:
                parts.append(f"*{body}*")
            else:
                parts.append(f"**{body}**")
        else:
            parts.append(inline(c))
    s = "".join(parts)
    s = re.sub(r'\\\s*\n\s*', "<br>\n", s)
    return s.strip()


def render_list(node, ordered=False):
    flat = inline(node)
    lines = [l.strip() for l in flat.split("\n") if l.strip()]
    out = []
    for i, l in enumerate(lines, 1):
        out.append(f"{i}. {l}" if ordered else f"- {l}")
    return "\n".join(out)


def render_table(node):
    rows = []
    for r in node["children"]:
        if r.get("tag") != "TableRow":
            continue
        cells = []
        for c in r["children"]:
            if c.get("tag") == "TableCell":
                cells.append(inline(c).replace("\n", " ").replace("|", "\\|"))
        rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |",
           "|" + "|".join([" --- "] * width) + "|"]
    for r in rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def render_code(node):
    inner = "".join(c.get("text", "") for c in node["children"])
    inner = textwrap.dedent(inner).strip("\n")
    return inner


def quote(text):
    return "\n".join("> " + l if l.strip() else ">" for l in text.split("\n"))


def render(node):
    blocks = []
    num_run = 0
    for c in node["children"]:
        if "text" in c:
            if c["text"].strip():
                blocks.append(c["text"].strip())
                num_run = 0
            continue
        t = c["tag"]
        if t == "NumberedList":
            num_run += 1
            flat = inline(c)
            lines = [l.strip() for l in flat.split("\n") if l.strip()]
            blocks.append("\n".join(f"{num_run + i}. {l}" for i, l in enumerate(lines)))
            continue
        if t != "BulletedList":
            num_run = 0
        if t == "Heading":
            lvl = int(attr(c, "level", "2"))
            blocks.append("#" * lvl + " " + inline(c))
        elif t == "Paragraph":
            blocks.append(inline(c))
        elif t == "Divider":
            blocks.append("---")
        elif t == "BulletedList":
            blocks.append(render_list(c, False))
        elif t == "BlockQuote":
            blocks.append(quote(render(c)))
        elif t == "Table":
            blocks.append(render_table(c))
        elif t == "Code":
            blocks.append(render_code(c))
        elif t == "Todo":
            checked = "checked" in (c.get("attrs") or "")
            blocks.append(("- [x] " if checked else "- [ ] ") + inline(c))
        else:
            sub = render(c)
            if sub:
                blocks.append(sub)
    md = "\n\n".join(b for b in blocks if b.strip())
    md = re.sub(r'\n\n(?=(?:- |\d+\. )\S)', '\n', md)
    return md


def tidy(md):
    md = re.sub(r'\n{3,}', '\n\n', md)
    md = re.sub(r'[ \t]+\n', '\n', md)
    return md.strip() + "\n"


def main():
    import argparse
    ap = argparse.ArgumentParser(description="资料库 doc 组件语法 → Markdown")
    ap.add_argument("--src", default=RAW, help="*.raw 所在目录")
    ap.add_argument("--out", default=OUT, help="输出 .md 目录")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    n = 0
    for f in sorted(os.listdir(a.src)):
        if not f.endswith(".raw"):
            continue
        src = open(os.path.join(a.src, f), encoding="utf-8").read()
        md = tidy(render(parse(strip_wrapper(src))))
        out = f[:-4]
        open(os.path.join(a.out, out), "w", encoding="utf-8").write(md)
        print(f"{len(md):>7}B  {out}")
        n += 1
    print(f"\n共转换 {n} 个文件 → {a.out}")


if __name__ == "__main__":
    main()
