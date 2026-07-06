from flask import Flask, render_template, request, send_from_directory, url_for, redirect
from yt_dlp import YoutubeDL
import os
import uuid
import glob
import subprocess
import time
import threading
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(__file__)
TMP_DIR = os.path.join(BASE_DIR, 'tmp')
os.makedirs(TMP_DIR, exist_ok=True)

# in-memory mapping: filename -> {'path': ..., 'expires_at': unix_ts}
DOWNLOADS = {}


def cleanup_expired_files(interval_seconds=60):
    while True:
        now = time.time()
        to_remove = []
        for fname, meta in list(DOWNLOADS.items()):
            if meta.get('expires_at') and meta['expires_at'] <= now:
                try:
                    if os.path.exists(meta['path']):
                        os.remove(meta['path'])
                except Exception:
                    pass
                to_remove.append(fname)
        for f in to_remove:
            DOWNLOADS.pop(f, None)
        time.sleep(interval_seconds)


# start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_expired_files, daemon=True)
cleanup_thread.start()

app = Flask(__name__, template_folder='templates')


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/info', methods=['POST'])
def info():
    url = request.form.get('url')
    if not url:
        return render_template('index.html', error='Please provide a video URL')

    ydl_opts = {'skip_download': True, 'quiet': True, 'no_warnings': True}
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return render_template('index.html', error=str(e))

    # handle playlists by taking the first entry
    if isinstance(info, dict) and 'entries' in info and info['entries']:
        info = info['entries'][0]

    title = info.get('title')
    thumbnail = info.get('thumbnail')
    formats = info.get('formats', []) or []

    # collect video formats with resolution information
    formats_filtered = []
    for f in formats:
        # include video tracks (skip audio-only)
        if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
            # skip audio-only formats for this prototype
            continue
        resolution = f.get('resolution') or (str(f.get('height')) + 'p' if f.get('height') else None)
        formats_filtered.append({
            'format_id': f.get('format_id'),
            'ext': f.get('ext'),
            'resolution': resolution,
            'fps': f.get('fps'),
        })

    # dedupe by (resolution, ext), prefer higher fps when available
    seen = set()
    formats_sorted = sorted(formats_filtered, key=lambda x: ((x['resolution'] or ''), (x['ext'] or ''), x['fps'] or 0), reverse=True)
    final_formats = []
    for f in formats_sorted:
        key = (f['resolution'], f['ext'])
        if key in seen:
            continue
        seen.add(key)
        final_formats.append(f)

    return render_template('result.html', title=title, thumbnail=thumbnail, formats=final_formats, url=url)


@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    format_id = request.form.get('format_id')
    target = request.form.get('target') or 'original'  # original, mp4, webm
    expiry_minutes = int(request.form.get('expiry_minutes') or 15)
    if not url or not format_id:
        return redirect(url_for('index'))

    unique = uuid.uuid4().hex
    outtmpl = os.path.join(TMP_DIR, unique + '.%(ext)s')
    ydl_opts = {'format': format_id, 'outtmpl': outtmpl, 'quiet': True, 'no_warnings': True}

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as e:
        return render_template('index.html', error=f'Download failed: {e}')

    # find the downloaded file (first match)
    matches = glob.glob(os.path.join(TMP_DIR, unique + '.*'))
    if not matches:
        return render_template('index.html', error='Downloaded file not found')

    downloaded = matches[0]
    orig_ext = os.path.splitext(downloaded)[1].lstrip('.')

    final_path = downloaded
    if target != 'original' and target != orig_ext:
        # re-encode using ffmpeg
        target_path = os.path.join(TMP_DIR, unique + '.' + target)
        cmd = ['ffmpeg', '-y', '-i', downloaded, '-c:v', 'libx264' if target == 'mp4' else 'libvpx-vp9', '-c:a', 'aac' if target == 'mp4' else 'libvorbis', target_path]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            final_path = target_path
        except subprocess.CalledProcessError as e:
            return render_template('index.html', error=f'FFmpeg failed: {e.stderr.decode(errors="ignore")}')

    filename = os.path.basename(final_path)

    # register download with expiry
    expires_at = time.time() + (expiry_minutes * 60)
    DOWNLOADS[filename] = {'path': final_path, 'expires_at': expires_at}

    download_url = url_for('serve_file', filename=filename)
    expires_dt = datetime.fromtimestamp(expires_at)
    return render_template('result.html', title='Download ready', thumbnail=None, formats=[], url=url, download_url=download_url, filename=filename, expires_at=expires_dt)


@app.route('/files/<path:filename>', methods=['GET'])
def serve_file(filename):
    # check mapping and expiry
    meta = DOWNLOADS.get(filename)
    now = time.time()
    if not meta:
        return render_template('index.html', error='File not found or expired')
    if meta.get('expires_at') and meta['expires_at'] <= now:
        # cleanup
        try:
            if os.path.exists(meta['path']):
                os.remove(meta['path'])
        except Exception:
            pass
        DOWNLOADS.pop(filename, None)
        return render_template('index.html', error='Link has expired')

    # send file as attachment
    return send_from_directory(TMP_DIR, filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5001)
