#!/usr/bin/env python3
"""agent-skills-bridge — 只读体检：本机所有 agent skill root vs WorkBuddy

输出四段：
  ① 各 skill root 数量
  ② WorkBuddy 已加载数
  ③ 差集：外部有、WorkBuddy 没有
  ④ 差集里「绑定的 CLI 本机已装」的（最该处理的一批）
  ⑤ 断链：已装 skill 引用的兄弟 skill 不存在

不修改任何文件。桥接动作由 agent 按 SKILL.md 手动执行。
"""
import os
import glob
import re

HOME = os.path.expanduser("~")
WS = os.path.join(HOME, "Documents/hermes_vault_clean")

FAIL = 0


def skill_names(p):
    """目录下带 SKILL.md 的子目录名（含软链）"""
    if not os.path.isdir(p):
        return set()
    out = set()
    for e in os.listdir(p):
        fp = os.path.join(p, e)
        if os.path.isdir(fp) and (
            os.path.exists(os.path.join(fp, "SKILL.md")) or os.path.islink(fp)
        ):
            out.add(e)
    return out


def nested(patt):
    """<root>/skills/<cat>/<name> -> {name: [relpath]}"""
    out = {}
    for cat in glob.glob(patt):
        if not os.path.isdir(cat):
            continue
        for e in os.listdir(cat):
            fp = os.path.join(cat, e)
            if os.path.isdir(fp) and os.path.exists(os.path.join(fp, "SKILL.md")):
                out.setdefault(e, []).append(os.path.relpath(fp, HOME))
    return out


ROOTS = {
    "~/.claude/skills": os.path.join(HOME, ".claude/skills"),
    "~/.agents/skills": os.path.join(HOME, ".agents/skills"),
    "~/.hermes/skills": os.path.join(HOME, ".hermes/skills"),
    "~/.codex/skills": os.path.join(HOME, ".codex/skills"),
    "~/.cursor/skills": os.path.join(HOME, ".cursor/skills"),
    "~/.gemini/skills": os.path.join(HOME, ".gemini/skills"),
    "~/.continue/skills": os.path.join(HOME, ".continue/skills"),
    "~skills": os.path.join(HOME, "skills"),
}

ext_simple = {k: skill_names(v) for k, v in ROOTS.items()}
prof = nested(os.path.join(HOME, ".hermes/profiles/*/skills/*"))
plug = nested(os.path.join(HOME, ".workbuddy/plugins/cache/*/*/*/skills"))

# WorkBuddy 实际会加载的
wb = set(skill_names(os.path.join(HOME, ".workbuddy/skills")))
wb |= skill_names(os.path.join(WS, ".workbuddy/skills"))
wb |= set(plug.keys())
wb |= skill_names(
    "/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked"
    "/resources/plugins/workbuddy-builtin/skills"
)

print("=" * 64)
print("agent-skills-bridge — 本机 skill 体检（只读）")
print("=" * 64)
print()
print("① 各 root 数量")
for k, v in ext_simple.items():
    print(f"   {k:<26} {len(v):>4}")
print(f"   {'hermes-profiles':<26} {len(prof):>4}")
print(f"   {'WorkBuddy plugin (自动加载)':<26} {len(plug):>4}")
print()
print(f"② WorkBuddy 已加载 skill：{len(wb)}")
print()

all_ext = {}
for label, s in ext_simple.items():
    for n in s:
        all_ext.setdefault(n, set()).add(label)
for n in prof:
    all_ext.setdefault(n, set()).add("hermes-profile")

missing = {n: sorted(locs) for n, locs in all_ext.items() if n not in wb}
print(f"③ 差集（外部有、WorkBuddy 没有）：{len(missing)} 个")
print()

# ④ 已装 CLI 匹配
installed = set()
for d in [os.path.join(HOME, ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin",
          os.path.join(HOME, ".opencode/bin")]:
    if os.path.isdir(d):
        installed |= {e.lower() for e in os.listdir(d)}

# 太泛的 token 会带来误报（code / agent / node…），排除
STOP = {"code", "agent", "node", "line", "data", "file", "text", "time",
        "open", "test", "user", "page", "head", "the", "and", "for", "run"}

hits = []
for n, locs in sorted(missing.items()):
    for t in n.lower().replace("_", "-").split("-"):
        if len(t) >= 3 and t in installed and t not in STOP:
            hits.append((n, t))
            break

print(f"④ ⭐ 其中「绑定的 CLI 本机已装」：{len(hits)} 个 ← 优先处理")
cur = None
for n, t in hits:
    if t != cur:
        print(f"   ── CLI: {t}")
        cur = t
    print(f"      {n}")
print()

# ⑤ 断链：已装 skill 引用的「兄弟 skill」不存在
print("⑤ 断链检查（同前缀族的 /skill-name 引用）")
root = os.path.join(HOME, ".workbuddy/skills")
present = {e for e in os.listdir(root)} if os.path.isdir(root) else set()
# 前缀族 = 现有 skill 名的第一个 '-' 之前的部分
families = {n.split("-")[0] for n in present if "-" in n}

# 只认「独立出现」的 /slug：前面不能是路径字符（排除 a/b/slug 这类普通路径）
REF = re.compile(r"(?<![\w/.~-])/([a-z0-9]+(?:-[a-z0-9]+)+)")

broken = set()
for n in sorted(present):
    for candidate in (os.path.join(root, n, "SKILL.md"),):
        if not os.path.isfile(candidate):
            continue
        try:
            txt = open(candidate, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for slug in REF.findall(txt):
            if slug.split("-")[0] not in families:
                continue          # 前缀不属任何 skill 族 -> 概念/命令名，跳过
            if slug in present:
                continue
            broken.add(slug)

if broken:
    for b in sorted(broken):
        print(f"   ⚠️ {b}")
else:
    print("   （无）")
print()
print(f"提示：桥接用 ln -s（软链跟随上游升级）。新装 skill 下个会话才生效。")
print(f"退出码: {FAIL}")
