from flask import Flask, render_template, request, send_from_directory, url_for, redirect
from yt_dlp import YoutubeDL
from werkzeug.utils import secure_filename
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


def format_size(size_bytes):
    if not size_bytes:
        return "—"
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


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


def save_uploaded_cookies(request_obj):
    cookies_file = request_obj.files.get('cookies_file')
    if not cookies_file or not getattr(cookies_file, 'filename', ''):
        return None
    safe_name = secure_filename(cookies_file.filename) or 'cookies.txt'
    path = os.path.join(TMP_DIR, f"{uuid.uuid4().hex}_{safe_name}")
    cookies_file.save(path)
    return path


def build_yt_dlp_options(cookies_path=None, skip_download=False):
    options = {'quiet': True, 'no_warnings': True, 'nplaylist': True}
    if skip_download:
        options['skip_download'] = True
    if cookies_path:
        options['cookiefile'] = cookies_path
    return options


def explain_yt_dlp_error(error):
    message = str(error).lower()
    if 'not a bot' in message or 'confirm you’re not a bot' in message or 'captcha' in message or 'sign in to confirm' in message:
        return (
            'YouTube is blocking this request from the server. '
            'If you have a browser cookies file, upload it here to try again. '
            'Otherwise, try a different video source or wait a bit and try again.'
        )
    return str(error)


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

    cookies_path = None
    try:
        cookies_path = save_uploaded_cookies(request)
        ydl_opts = build_yt_dlp_options(cookies_path=cookies_path, skip_download=True)
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return render_template('index.html', error=explain_yt_dlp_error(e))
    finally:
        if cookies_path and os.path.exists(cookies_path):
            os.remove(cookies_path)

    # handle playlists by taking the first entry
    if isinstance(info, dict) and 'entries' in info and info['entries']:
        info = info['entries'][0]

    title = info.get('title')
    thumbnail = info.get('thumbnail')
    formats = info.get('formats', []) or []

    formats_filtered = []
    for f in formats:
        if f.get('vcodec') == 'none':
            continue
        if not f.get('height'):
            continue
        resolution = f.get('resolution') or f"{f.get('height')}p"
        size_bytes = f.get('filesize') or f.get('filesize_approx')
        formats_filtered.append({
            'format_id': f.get('format_id'),
            'ext': f.get('ext'),
            'resolution': resolution,
            'height': f.get('height'),
            'size': format_size(size_bytes),
            'size_bytes': size_bytes,
        })

    # keep the most common quality tiers only (up to 5)
    formats_sorted = sorted(formats_filtered, key=lambda x: x['height'], reverse=True)
    seen_heights = set()
    final_formats = []
    for f in formats_sorted:
        if f['height'] in seen_heights:
            continue
        seen_heights.add(f['height'])
        final_formats.append(f)
        if len(final_formats) >= 5:
            break

    return render_template('result.html', title=title, thumbnail=thumbnail, formats=final_formats, url=url)


@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    quality = request.form.get('quality')
    target = request.form.get('target') or 'mp4'
    expiry_minutes = int(request.form.get('expiry_minutes') or 15)
    if not url or not quality:
        return redirect(url_for('index'))

    quality_height = int(quality)
    container = target if target in ('mp4', 'webm') else 'mp4'
    format_selector = f"best[height<={quality_height}][ext={container}]/best[height<={quality_height}]/best"

    unique = uuid.uuid4().hex
    outtmpl = os.path.join(TMP_DIR, unique + '.%(ext)s')
    ydl_opts = {
        'format': format_selector,
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }

    cookies_path = None
    try:
        cookies_path = save_uploaded_cookies(request)
        ydl_opts = dict(ydl_opts)
        if cookies_path:
            ydl_opts['cookiefile'] = cookies_path
        with YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as e:
        return render_template('index.html', error=f'Download failed: {explain_yt_dlp_error(e)}')
    finally:
        if cookies_path and os.path.exists(cookies_path):
            os.remove(cookies_path)

    matches = glob.glob(os.path.join(TMP_DIR, unique + '.*'))
    if not matches:
        return render_template('index.html', error='Downloaded file not found')

    downloaded = matches[0]
    final_path = downloaded
    filename = os.path.basename(final_path)

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
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', '5001'))
    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=8)
    except Exception:
        app.run(debug=False, host=host, port=port)
