#!/usr/bin/env python3
"""
 Agnes Video 2.5 Flash 一键跑一条（单 ref · 免费模型）。
 用法：
   python3 run_agnes_recipe.py \
       --prompt prompt.txt \
       --ref /path/to/ref.png \
       --ratio 16:9 --duration 5 \
       --outdir ./agnes-out

 依赖：opencli browser pavo 已连 Chrome、curl、ffmpeg（可选）。
"""

import argparse, json, os, pathlib, shlex, subprocess, sys, textwrap, time, urllib.parse

PROFILE = "pavo"
CORS_PORT = 8899
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"


def run(cmd, **kw):
    """运行 shell 命令，失败时抛异常。"""
    print("$", " ".join(shlex.quote(str(c)) for c in cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print("ERR:", r.stderr[:800] if r.stderr else r.stdout[:800], file=sys.stderr)
        raise RuntimeError(f"command failed: {cmd}")
    return r.stdout


def browser_eval(js: str, timeout: int = 30):
    """用 opencli browser pavo eval 执行 JS，返回字符串。"""
    return run(["opencli", "browser", PROFILE, "eval", js], timeout=timeout)


def ensure_cors_server(ref_path: str):
    """确保 127.0.0.1:8899 在serve参考图所在目录。"""
    root = os.path.dirname(os.path.abspath(ref_path))
    # 先探测是否已有服务
    try:
        r = subprocess.run(
            ["curl", "-s", "--noproxy", "*", f"http://127.0.0.1:{CORS_PORT}/"],
            capture_output=True, timeout=3
        )
        if r.returncode == 0 and r.status_code is None:
            # curl 没有 -w，通过内容判断；只要通就行
            return
    except Exception:
        pass

    script = textwrap.dedent(f'''\
        import http.server, socketserver
        ROOT = {root!r}
        class H(http.server.SimpleHTTPRequestHandler):
            def __init__(self,*a,**k): super().__init__(*a, directory=ROOT, **k)
            def end_headers(self):
                self.send_header("Access-Control-Allow-Origin","*")
                self.send_header("Access-Control-Allow-Private-Network","true")
                super().end_headers()
        socketserver.TCPServer.allow_reuse_address = True
        socketserver.ThreadingTCPServer(("127.0.0.1",{CORS_PORT}),H).serve_forever()
    ''')
    script_path = "/tmp/serve_cors_agnes.py"
    with open(script_path, "w") as f:
        f.write(script)
    subprocess.Popen(
        ["/usr/bin/python3", script_path],
        stdout=open("/tmp/serve_cors_agnes.log", "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    # 等待服务可用
    for _ in range(30):
        try:
            r = subprocess.run(
                ["curl", "-s", "--noproxy", "*", "-o", "/dev/null", "-w", "%{http_code}",
                 f"http://127.0.0.1:{CORS_PORT}/"],
                capture_output=True, text=True, timeout=3
            )
            if r.stdout.strip() == "200":
                return
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError("CORS server failed to start")


def open_new_chat():
    run(["opencli", "browser", PROFILE, "open", "https://app.pavo-ai.cn/chat", "--window", "background"])
    time.sleep(4)


def set_model_flash():
    """把模型下拉设成 Agnes Video 2.5 Flash。"""
    js = """
    (async () => {
      const sel = document.querySelectorAll('.ant-select')[1];
      const tr = sel && sel.querySelector('.ant-select-selector');
      ['mousedown','mouseup','click'].forEach(t => tr.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window})));
      await new Promise(r=>setTimeout(r,900));
      const opts = [...document.querySelectorAll('.ant-select-dropdown .ant-select-item-option')];
      const wanted = opts.find(e => e.innerText.includes('Agnes Video 2.5 Flash'));
      if (wanted) { wanted.click(); return 'set_flash'; }
      return 'already_or_missing';
    })()
    """
    browser_eval(js)
    time.sleep(1)


def set_params(ratio: str, duration: int):
    """点开设置面板，选比例、时长、720P。"""
    js_open = """
    (async () => {
      const b = document.querySelector('#dle_setting');
      ['mousedown','mouseup','click'].forEach(t => b.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window})));
      await new Promise(r=>setTimeout(r,800));
      return 'opened';
    })()
    """
    browser_eval(js_open)
    time.sleep(0.8)

    def pick(label):
        return f"""
        (async () => {{
          const P = [...document.querySelectorAll('.ant-popover')].filter(e=>e.offsetHeight>0).pop();
          if (!P) return 'no_panel';
          const btn = [...P.querySelectorAll('button')].find(b => b.innerText.trim() === {json.dumps(label)});
          if (btn) {{ btn.click(); return 'ok:{label}'; }}
          return 'miss:{label}';
        }})()
        """

    browser_eval(pick(ratio))
    browser_eval(pick(f"{duration}s"))
    browser_eval(pick("720P"))
    time.sleep(0.5)
    # 关闭面板
    run(["opencli", "browser", PROFILE, "keys", "Escape"], timeout=10)
    time.sleep(0.5)


def upload_ref(ref_path: str):
    """通过 fetch 本地图 + DataTransfer 注入上传。"""
    basename = os.path.basename(ref_path)
    js = f"""
    (async () => {{
      try {{
        const r = await fetch('http://127.0.0.1:{CORS_PORT}/{urllib.parse.quote(basename)}', {{cache:'no-store'}});
        if (!r.ok) throw new Error('fetch ' + r.status);
        const blob = await r.blob();
        const f = new File([blob], {json.dumps(basename)}, {{type: blob.type || 'image/png'}});
        const dt = new DataTransfer(); dt.items.add(f);
        const i = document.querySelector('input[type=file]');
        if (!i) throw new Error('no file input');
        i.files = dt.files;
        i.dispatchEvent(new Event('input',  {{bubbles:true}}));
        i.dispatchEvent(new Event('change', {{bubbles:true}}));
        await new Promise(x=>setTimeout(x,3500));
        return JSON.stringify({{files: i.files.length, ok: true}});
      }} catch (e) {{
        return 'ERR: ' + e.message;
      }}
    }})()
    """
    out = browser_eval(js)
    print("upload result:", out[:200])


def send_prompt(prompt: str):
    run(["opencli", "browser", PROFILE, "fill",
         '[contenteditable=true][aria-label="Intelligent input area"]', prompt], timeout=30)
    time.sleep(0.5)
    run(["opencli", "browser", PROFILE, "click", "#dle_send_button"], timeout=30)
    time.sleep(3)


def wait_for_video(timeout_min: int = 8):
    """轮询，直到页面出现 video 标签。"""
    deadline = time.time() + timeout_min * 60
    while time.time() < deadline:
        # 重载页面刷新结果
        run(["opencli", "browser", PROFILE, "open", "https://app.pavo-ai.cn/chat", "--window", "background"], timeout=30)
        time.sleep(5)
        out = browser_eval("""
        (() => {
          const c = document.querySelector('#chat-page-container') || document.body;
          const v = [...c.querySelectorAll('video')].map(x => x.src || x.currentSrc).filter(Boolean);
          return JSON.stringify({v_count: v.length, last: v[v.length-1] || ''});
        })()
        """)
        print("poll:", out.strip())
        try:
            data = json.loads(out.strip().split('\n')[-1])
            if data.get('v_count', 0) > 0 and data.get('last', '').endswith('.mp4'):
                return data['last']
        except Exception:
            pass
        time.sleep(25)
    raise RuntimeError("timeout waiting for video")


def extract_first_frame():
    out = browser_eval("""
    (() => {
      const c = document.querySelector('#chat-page-container') || document.body;
      const imgs = [...c.querySelectorAll('img')].map(x => x.src).filter(s => /self-v03-first-frames/.test(s));
      return JSON.stringify({count: imgs.length, last: imgs[imgs.length-1] || ''});
    })()
    """)
    try:
        data = json.loads(out.strip().split('\n')[-1])
        return data.get('last', '')
    except Exception:
        return ''


def download(url: str, dest: str):
    run(["curl", "-s", "--noproxy", "*", "-A", UA, "-o", dest, url], timeout=120)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--ratio", default="16:9")
    ap.add_argument("--duration", type=int, default=5)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    prompt = pathlib.Path(args.prompt).read_text(encoding="utf-8").strip()
    ref_path = os.path.abspath(args.ref)
    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    print(f"=== Agnes run: ratio={args.ratio} duration={args.duration}s ref={ref_path}")

    ensure_cors_server(ref_path)
    open_new_chat()
    set_model_flash()
    set_params(args.ratio, args.duration)
    upload_ref(ref_path)
    send_prompt(prompt)

    print("submitted, waiting for video ...")
    video_url = wait_for_video()
    print("video URL:", video_url)

    first_frame_url = extract_first_frame()
    print("first frame URL:", first_frame_url)

    base = pathlib.Path(outdir)
    video_dest = base / "out.mp4"
    frame_dest = base / "firstframe.jpg"
    download(video_url, str(video_dest))
    if first_frame_url:
        download(first_frame_url, str(frame_dest))

    print(f"saved: {video_dest} ({os.path.getsize(video_dest)} bytes)")
    if first_frame_url:
        print(f"saved: {frame_dest} ({os.path.getsize(frame_dest)} bytes)")


if __name__ == "__main__":
    main()
