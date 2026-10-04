#!/usr/bin/env python3
"""Minimal MCP stdio probe — stdlib only.

Usage:
    python3 mcp_probe.py -- uvx reach-mcp --transport stdio
    python3 mcp_probe.py -- uvx reach-mcp --transport stdio --search "关键词" [--source bilibili]

Does: initialize handshake -> tools/list -> tools/call list_sources (if present)
      -> optional live search to prove a free source is actually alive.

Why hand-rolled: no third-party deps, and it surfaces the "one text block per
source" shape that most clients mis-parse.
"""
import argparse, json, os, queue, subprocess, sys, threading, time


def spawn(cmd):
    env = dict(os.environ)
    extra = os.path.expanduser("~/.local/bin")
    if extra not in env.get("PATH", ""):
        env["PATH"] = extra + ":" + env.get("PATH", "")
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
    q, errs = queue.Queue(), []
    threading.Thread(target=lambda: [q.put(l) for l in p.stdout], daemon=True).start()
    threading.Thread(target=lambda: [errs.append(l) for l in p.stderr], daemon=True).start()
    return p, q, errs


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--search")
    ap.add_argument("--source", default="bilibili")
    ap.add_argument("--timeout", type=int, default=300)
    ns, cmd = ap.parse_known_args()
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("need: -- <command...>", file=sys.stderr)
        return 2

    p, q, errs = spawn(cmd)

    def send(o):
        p.stdin.write(json.dumps(o) + "\n"); p.stdin.flush()

    def wait_id(tid, timeout=None):
        end = time.time() + (timeout or ns.timeout)
        while time.time() < end:
            try:
                line = q.get(timeout=1)
            except queue.Empty:
                if p.poll() is not None:
                    return {"__error__": "exited", "code": p.returncode}
                continue
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
            except Exception:
                continue
            if m.get("id") == tid:
                return m
        return {"__error__": "timeout"}

    def call(tid, name, args):
        send({"jsonrpc": "2.0", "id": tid, "method": "tools/call",
              "params": {"name": name, "arguments": args}})
        r = wait_id(tid)
        blocks = []
        for c in (r.get("result", {}).get("content") or []):
            try:
                blocks.append(json.loads(c["text"]))
            except Exception:
                blocks.append(c.get("text"))
        return blocks, r

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "probe", "version": "0.1"}}})
        init = wait_id(1)
        si = init.get("result", {}).get("serverInfo", {})
        print("=== initialize ===\nserver: %s v%s" % (si.get("name"), si.get("version")))
        if init.get("result", {}).get("instructions"):
            print("instructions:", init["result"]["instructions"][:400])
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tl = wait_id(2)
        tools = [t["name"] for t in tl.get("result", {}).get("tools", [])]
        print("\n=== tools (%d) ===\n%s" % (len(tools), ", ".join(tools)))

        if "list_sources" in tools:
            blocks, raw = call(3, "list_sources", {})
            rows = [b for b in blocks if isinstance(b, dict) and "name" in b]
            if rows:
                av = sorted(r["name"] for r in rows if r.get("available"))
                gt = sorted(r["name"] for r in rows if not r.get("available"))
                print("\n=== sources: %d total | %d available | %d gated ===" % (
                    len(rows), len(av), len(gt)))
                print("AVAILABLE: " + ", ".join(av))
                print("GATED:     " + ", ".join(gt))
                print("\n--- credential-gated detail ---")
                for r in sorted(rows, key=lambda x: x["name"]):
                    if r.get("needs_auth") or r.get("required_env"):
                        print("  %-14s avail=%-5s env=%s" % (
                            r["name"], r.get("available"),
                            ",".join(r.get("required_env") or []) or "-"))
            else:
                print("\n(list_sources raw) ", json.dumps(raw, ensure_ascii=False)[:800])

        if ns.search:
            print("\n=== live search %r on [%s] ===" % (ns.search, ns.source))
            items, raw = call(4, "search", {"query": ns.search, "sources": [ns.source],
                                            "days": 90, "max_per_source": 5,
                                            "synthesize": False})
            rows = []
            for b in items:
                if isinstance(b, dict) and b.get("items"):
                    rows += b["items"]
                elif isinstance(b, dict) and b.get("title"):
                    rows.append(b)
            print("rows: %d" % len(rows))
            for r in rows[:8]:
                print("  - %s | %s | score=%s" % (
                    str(r.get("title"))[:60], str(r.get("url"))[:55], r.get("score")))
            if not rows:
                print("  (none) raw:", json.dumps(raw, ensure_ascii=False)[:600])
    finally:
        p.terminate()
        time.sleep(0.5)
        tail = "".join(errs[-20:]).strip()
        if tail:
            print("\n=== stderr tail ===\n" + tail[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
