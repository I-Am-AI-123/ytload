import os, uuid, threading, json
from flask import Flask, request, jsonify, send_file, Response
import yt_dlp

app = Flask(__name__)
DOWNLOAD_DIR = "/tmp/ytdl"
COOKIES_PATH = "/tmp/ytdl/cookies.txt"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Track job progress in memory
jobs = {}  # job_id -> {status, log, file_path, filename}

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>YTDLOAD</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #0b0b0b;
    --surface: #111;
    --border: #1e1e1e;
    --border-hover: #2e2e2e;
    --red: #ff3c3c;
    --red-dim: #ff3c3c22;
    --green: #3ddc84;
    --yellow: #ffe066;
    --text: #e0e0e0;
    --muted: #555;
    --faint: #222;
  }

  html, body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Mono', monospace;
    min-height: 100vh;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: 48px 16px 80px;
  }

  .app {
    width: 100%;
    max-width: 660px;
    animation: fadeUp .5s ease both;
  }

  @keyframes fadeUp {
    from { opacity:0; transform:translateY(18px); }
    to   { opacity:1; transform:translateY(0); }
  }

  /* Header */
  .header { margin-bottom: 36px; }
  .logo {
    font-family: 'Syne', sans-serif;
    font-size: 2.6rem;
    font-weight: 800;
    color: #fff;
    letter-spacing: -2px;
    line-height: 1;
  }
  .logo span { color: var(--red); }
  .tagline {
    font-size: .68rem;
    color: var(--muted);
    letter-spacing: 2.5px;
    text-transform: uppercase;
    margin-top: 6px;
  }

  /* Card */
  .card {
    background: var(--surface);
    border: 1.5px solid var(--border);
    border-radius: 14px;
    padding: 28px;
    margin-bottom: 16px;
    box-shadow: 0 0 80px var(--red-dim);
  }

  .field + .field { margin-top: 20px; }
  label {
    display: block;
    font-size: .65rem;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 7px;
  }

  textarea, select {
    width: 100%;
    background: var(--bg);
    border: 1.5px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-family: 'DM Mono', monospace;
    font-size: .8rem;
    padding: 11px 14px;
    transition: border-color .2s;
    outline: none;
    resize: vertical;
  }
  textarea { height: 88px; }
  textarea:focus, select:focus { border-color: var(--red); }

  /* Toggle pills */
  .toggle-group {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .toggle-group input { display: none; }
  .toggle-group label {
    background: var(--bg);
    border: 1.5px solid var(--border);
    border-radius: 8px;
    padding: 9px 18px;
    font-size: .75rem;
    letter-spacing: .5px;
    text-transform: none;
    color: var(--muted);
    cursor: pointer;
    transition: all .15s;
    user-select: none;
  }
  .toggle-group input:checked + label {
    background: var(--red);
    border-color: var(--red);
    color: #fff;
  }
  .toggle-group label:hover { border-color: var(--border-hover); color: #aaa; }

  /* Quality row */
  #quality-row { transition: opacity .2s; }
  #quality-row.hidden { opacity: 0; pointer-events: none; height: 0; overflow: hidden; margin: 0; }

  /* Divider */
  .divider { border: none; border-top: 1px solid var(--border); margin: 24px 0; }

  /* Button */
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: var(--red);
    border: none;
    border-radius: 8px;
    color: #fff;
    font-family: 'DM Mono', monospace;
    font-size: .8rem;
    font-weight: 500;
    letter-spacing: .5px;
    padding: 11px 24px;
    cursor: pointer;
    transition: opacity .15s;
    text-decoration: none;
  }
  .btn:hover { opacity: .82; }
  .btn:disabled { background: var(--faint); color: #444; cursor: not-allowed; opacity: 1; }
  .btn.ghost {
    background: transparent;
    border: 1.5px solid var(--border);
    color: var(--muted);
  }
  .btn.ghost:hover { border-color: var(--border-hover); color: #aaa; }
  .btn-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }

  /* Progress */
  .progress-wrap { margin-top: 18px; }
  .progress-track {
    height: 4px;
    background: var(--faint);
    border-radius: 99px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: var(--red);
    border-radius: 99px;
    width: 0%;
    transition: width .3s;
  }
  .progress-fill.done { background: var(--green); }
  .progress-label {
    font-size: .68rem;
    color: var(--muted);
    margin-top: 6px;
  }

  /* Log */
  .log-wrap { margin-top: 20px; }
  .log {
    background: var(--bg);
    border: 1.5px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
    font-size: .71rem;
    line-height: 1.7;
    min-height: 70px;
    max-height: 220px;
    overflow-y: auto;
    color: var(--muted);
  }
  .log .ok   { color: var(--green); }
  .log .err  { color: var(--red); }
  .log .info { color: var(--yellow); }

  /* Cookies card */
  .cookie-status {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: .75rem;
    color: var(--muted);
    margin-top: 10px;
  }
  .cookie-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--faint);
    flex-shrink: 0;
  }
  .cookie-dot.active { background: var(--green); }
  .upload-label {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: transparent;
    border: 1.5px solid var(--border);
    border-radius: 8px;
    color: var(--muted);
    font-family: 'DM Mono', monospace;
    font-size: .78rem;
    padding: 9px 18px;
    cursor: pointer;
    transition: all .15s;
  }
  .upload-label:hover { border-color: var(--border-hover); color: #aaa; }
  #cookie-file { display: none; }
  .cookie-hint {
    font-size: .68rem;
    color: #333;
    margin-top: 10px;
    line-height: 1.6;
  }
  .cookie-hint a { color: #555; }

  #download-card { display: none; }
  #download-card.visible { display: block; }
  .dl-file {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 16px;
    background: var(--bg);
    border: 1.5px solid var(--border);
    border-radius: 10px;
  }
  .dl-filename {
    font-size: .78rem;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
  }
</style>
</head>
<body>
<div class="app">

  <div class="header">
    <div class="logo">YT<span>↓</span>LOAD</div>
    <div class="tagline">YouTube Downloader</div>
  </div>

  <div class="card">
    <div class="field">
      <label>URL — one per line</label>
      <textarea id="urls" placeholder="https://www.youtube.com/watch?v=&#10;https://www.youtube.com/playlist?list=..."></textarea>
    </div>

    <div class="field">
      <label>Format</label>
      <div class="toggle-group">
        <input type="radio" name="mode" id="m-video" value="video" checked>
        <label for="m-video">🎬 Video (MP4)</label>
        <input type="radio" name="mode" id="m-audio" value="audio">
        <label for="m-audio">🎵 Audio (MP3)</label>
        <input type="radio" name="mode" id="m-best" value="best">
        <label for="m-best">⚡ Best Available</label>
      </div>
    </div>

    <div class="field" id="quality-row">
      <label>Quality</label>
      <select id="quality">
        <option value="bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best">Best quality</option>
        <option value="bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]">1080p</option>
        <option value="bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]">720p</option>
        <option value="bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]">480p</option>
        <option value="bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]">360p</option>
      </select>
    </div>

    <hr class="divider">

    <div class="btn-row">
      <button class="btn" id="dl-btn" onclick="startDownload()">Download</button>
    </div>

    <div class="progress-wrap" id="progress-wrap" style="display:none">
      <div class="progress-track"><div class="progress-fill" id="progress-fill"></div></div>
      <div class="progress-label" id="progress-label">Starting…</div>
    </div>

    <div class="log-wrap">
      <label>Log</label>
      <div class="log" id="log">Waiting…</div>
    </div>
  </div>

  <div class="card" id="download-card">
    <label>Ready to save</label>
    <div id="file-list"></div>
  </div>

  <div class="card">
    <label>YouTube cookies</label>
    <div class="cookie-status">
      <div class="cookie-dot" id="cookie-dot"></div>
      <span id="cookie-label">No cookies uploaded</span>
    </div>
    <div style="display:flex;gap:10px;margin-top:14px;flex-wrap:wrap;align-items:center">
      <label class="upload-label" for="cookie-file">Upload cookies.txt</label>
      <input type="file" id="cookie-file" accept=".txt">
      <button class="btn ghost" id="delete-cookies" style="display:none" onclick="deleteCookies()">Remove</button>
    </div>
    <p class="cookie-hint">
      YouTube blocks server IPs without a valid session. Export your cookies using the
      <a href="https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc" target="_blank">Get cookies.txt Locally</a>
      Chrome extension while logged into YouTube, then upload the file here.
    </p>
  </div>

</div>

<script>
  // Show/hide quality based on mode
  document.querySelectorAll('input[name="mode"]').forEach(r => {
    r.addEventListener('change', () => {
      document.getElementById('quality-row').classList.toggle('hidden', r.value !== 'video');
    });
  });

  let pollTimer = null;

  function log(msg, cls='') {
    const el = document.getElementById('log');
    el.innerHTML += `<span class="${cls}">${msg}</span>\n`;
    el.scrollTop = el.scrollHeight;
  }

  function setProgress(pct, label) {
    const fill = document.getElementById('progress-fill');
    fill.style.width = pct + '%';
    fill.classList.toggle('done', pct >= 100);
    document.getElementById('progress-label').textContent = label;
  }

  async function startDownload() {
    const urls = document.getElementById('urls').value.trim().split('\n').filter(u => u.trim());
    if (!urls.length) { alert('Paste at least one URL.'); return; }

    const mode    = document.querySelector('input[name="mode"]:checked').value;
    const quality = document.getElementById('quality').value;

    document.getElementById('dl-btn').disabled = true;
    document.getElementById('progress-wrap').style.display = 'block';
    document.getElementById('download-card').classList.remove('visible');
    document.getElementById('log').innerHTML = '';
    document.getElementById('file-list').innerHTML = '';
    setProgress(0, 'Starting…');

    log('Sending request…', 'info');

    const res  = await fetch('/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls, mode, quality })
    });
    const { job_id } = await res.json();
    pollJob(job_id);
  }

  function pollJob(job_id) {
    pollTimer = setInterval(async () => {
      const res  = await fetch(`/status/${job_id}`);
      const data = await res.json();

      // Update log with new lines
      if (data.log) {
        document.getElementById('log').innerHTML = '';
        data.log.forEach(({ msg, cls }) => log(msg, cls));
      }

      if (data.progress != null) setProgress(data.progress, data.progress_label || '');

      if (data.status === 'done') {
        clearInterval(pollTimer);
        setProgress(100, 'Complete!');
        document.getElementById('dl-btn').disabled = false;
        showFiles(data.files, job_id);
      } else if (data.status === 'error') {
        clearInterval(pollTimer);
        document.getElementById('dl-btn').disabled = false;
      }
    }, 800);
  }

  async function checkCookies() {
    const res = await fetch('/cookies-status');
    const { has_cookies } = await res.json();
    document.getElementById('cookie-dot').classList.toggle('active', has_cookies);
    document.getElementById('cookie-label').textContent = has_cookies ? 'cookies.txt loaded' : 'No cookies uploaded';
    document.getElementById('delete-cookies').style.display = has_cookies ? 'inline-flex' : 'none';
  }

  document.getElementById('cookie-file').addEventListener('change', async function() {
    if (!this.files[0]) return;
    const fd = new FormData();
    fd.append('cookies', this.files[0]);
    const res = await fetch('/upload-cookies', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.ok) checkCookies();
    else alert('Upload failed: ' + data.error);
    this.value = '';
  });

  async function deleteCookies() {
    await fetch('/delete-cookies', { method: 'POST' });
    checkCookies();
  }

  checkCookies();

    if (!files || !files.length) return;
    const card = document.getElementById('download-card');
    const list = document.getElementById('file-list');
    list.innerHTML = '';
    files.forEach(fname => {
      list.innerHTML += `
        <div class="dl-file">
          <span class="dl-filename">📄 ${fname}</span>
          <a class="btn" href="/file/${job_id}/${encodeURIComponent(fname)}">Save</a>
        </div>`;
    });
    card.classList.add('visible');
  }
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return HTML

@app.route("/upload-cookies", methods=["POST"])
def upload_cookies():
    f = request.files.get("cookies")
    if not f:
        return jsonify({"ok": False, "error": "No file received"}), 400
    f.save(COOKIES_PATH)
    return jsonify({"ok": True})

@app.route("/cookies-status")
def cookies_status():
    return jsonify({"has_cookies": os.path.exists(COOKIES_PATH)})

@app.route("/delete-cookies", methods=["POST"])
def delete_cookies():
    if os.path.exists(COOKIES_PATH):
        os.remove(COOKIES_PATH)
    return jsonify({"ok": True})

@app.route("/download", methods=["POST"])
def download():
    data    = request.json
    urls    = data.get("urls", [])
    mode    = data.get("mode", "video")
    quality = data.get("quality", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best")

    job_id  = str(uuid.uuid4())
    job_dir = os.path.join(DOWNLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    jobs[job_id] = {"status": "running", "log": [], "progress": 0,
                    "progress_label": "Starting…", "files": []}

    def add_log(msg, cls=""):
        jobs[job_id]["log"].append({"msg": msg, "cls": cls})

    def progress_hook(d):
        if d["status"] == "downloading":
            pct_str = d.get("_percent_str", "0%").strip().replace("%", "")
            try: jobs[job_id]["progress"] = int(float(pct_str))
            except: pass
            speed = d.get("_speed_str", "").strip()
            eta   = d.get("_eta_str", "").strip()
            jobs[job_id]["progress_label"] = f"{pct_str}%  {speed}  ETA {eta}"
        elif d["status"] == "finished":
            jobs[job_id]["progress"] = 100
            add_log(f"✔ {os.path.basename(d['filename'])}", "ok")

    def run():
        if mode == "audio":
            opts = {
                "format": "bestaudio/best",
                "outtmpl": f"{job_dir}/%(title)s.%(ext)s",
                "postprocessors": [{"key": "FFmpegExtractAudio",
                                    "preferredcodec": "mp3", "preferredquality": "192"}],
                "progress_hooks": [progress_hook],
            }
        elif mode == "video":
            opts = {
                "format": quality,
                "outtmpl": f"{job_dir}/%(title)s.%(ext)s",
                "merge_output_format": "mp4",
                "progress_hooks": [progress_hook],
            }
        else:
            opts = {
                "format": "best",
                "outtmpl": f"{job_dir}/%(title)s.%(ext)s",
                "progress_hooks": [progress_hook],
            }

        if os.path.exists(COOKIES_PATH):
            opts["cookiefile"] = COOKIES_PATH
            add_log("Using cookies file for authentication.", "info")

        add_log(f"Starting {len(urls)} URL(s) in [{mode}] mode…", "info")
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download(urls)
            files = os.listdir(job_dir)
            jobs[job_id]["files"]  = files
            jobs[job_id]["status"] = "done"
            jobs[job_id]["progress"] = 100
            jobs[job_id]["progress_label"] = "Complete!"
            add_log(f"Done! {len(files)} file(s) ready.", "ok")
        except Exception as e:
            jobs[job_id]["status"] = "error"
            add_log(f"Error: {e}", "err")

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})

@app.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id, {})
    return jsonify({
        "status":         job.get("status", "unknown"),
        "log":            job.get("log", []),
        "progress":       job.get("progress", 0),
        "progress_label": job.get("progress_label", ""),
        "files":          job.get("files", []),
    })

@app.route("/file/<job_id>/<filename>")
def serve_file(job_id, filename):
    path = os.path.join(DOWNLOAD_DIR, job_id, filename)
    if not os.path.exists(path):
        return "File not found", 404
    return send_file(path, as_attachment=True, download_name=filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
