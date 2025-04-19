#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, shutil, tempfile
from flask import Flask, request, render_template, send_file
from werkzeug.utils import secure_filename
from yt_dlp import YoutubeDL

app = Flask(__name__)

def sanitize(s):
    return re.sub(r'[\\/:*?"<>|]', '_', s)

def extract_info(url, cookiefile=None):
    """Lấy metadata (skip download), có thể dùng cookie."""
    opts = {'skip_download': True}
    if cookiefile:
        opts['cookiefile'] = cookiefile
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)

def list_audio_formats(info):
    if 'formats' not in info and 'entries' in info:
        info = (info['entries'] or [info])[0]
    fmts = [f for f in info['formats'] if f.get('vcodec') == 'none']
    fmts.sort(key=lambda f: (f.get('abr') or f.get('tbr') or 0), reverse=True)
    return [
        {'format_id': f['format_id'], 'ext': f['ext'],
         'bitrate': f.get('abr') or f.get('tbr') or 0}
        for f in fmts
    ]

def download_media(url, mode, cookiefile=None):
    info = extract_info(url, cookiefile)
    is_playlist = info.get('_type') == 'playlist'
    tmp = tempfile.TemporaryDirectory()
    base = tmp.name

    if is_playlist:
        title = sanitize(info.get('playlist_title') or info.get('title') or 'playlist')
        folder = os.path.join(base, title)
        os.makedirs(folder, exist_ok=True)
        outtmpl = os.path.join(folder, '%(playlist_index)s - %(title)s.%(ext)s')
        noplay = False
    else:
        folder = base
        outtmpl = os.path.join(folder, '%(title)s.%(ext)s')
        noplay = True

    if mode == 'audio':
        fmt, merge = 'bestaudio', False
    elif mode == 'video_only':
        fmt, merge = 'bestvideo[ext=mp4]', False
    else:
        fmt, merge = 'bestvideo[ext=mp4]+bestaudio/best', True

    opts = {'format': fmt, 'outtmpl': outtmpl, 'noplaylist': noplay}
    if merge:
        opts['merge_output_format'] = 'mp4'
    if cookiefile:
        opts['cookiefile'] = cookiefile

    with YoutubeDL(opts) as ydl:
        ydl.download([url])

    # Trả file hoặc zip
    if not is_playlist:
        file = os.listdir(folder)[0]
        return os.path.join(folder, file)
    zip_path = shutil.make_archive(os.path.join(base, 'result'), 'zip', root_dir=folder)
    return zip_path

@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        url  = request.form.get('url', '').strip()
        mode = request.form.get('mode')

        # Lưu tạm cookie nếu có upload
        cookiefile = None
        uploaded = request.files.get('cookiefile')
        if uploaded and uploaded.filename:
            tmpdir = tempfile.mkdtemp()
            fname = secure_filename(uploaded.filename)
            cookiefile = os.path.join(tmpdir, fname)
            uploaded.save(cookiefile)

        # Bước 1: liệt kê định dạng audio nếu cần
        if mode == 'audio' and 'download_audio' not in request.form:
            try:
                info = extract_info(url, cookiefile)
                fmts = list_audio_formats(info)
            except Exception as e:
                return f"Error: {e}", 500
            return render_template('audio_formats.html', url=url, fmts=fmts)

        # Bước 2: thực download
        try:
            result = download_media(url, mode, cookiefile)
            filename = os.path.basename(result)
            return send_file(result, as_attachment=True, download_name=filename)
        except Exception as e:
            return f"Error khi tải: {e}", 500
        finally:
            # Cleanup cookie tmpdir
            if cookiefile:
                shutil.rmtree(os.path.dirname(cookiefile), ignore_errors=True)

    return render_template('index.html')

if __name__ == '__main__':
    # Port do Render gán vào biến môi trường PORT
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
