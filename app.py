#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import shutil
import tempfile
from flask import Flask, request, render_template, send_file, abort
from yt_dlp import YoutubeDL

app = Flask(__name__)

# ----- PHẦN CORE CHÍNH ----- #

def sanitize(string):
    """Loại bỏ ký tự không hợp lệ trong tên thư mục/file."""
    return re.sub(r'[\\/:*?"<>|]', '_', string)

def list_audio_formats(info):
    """
    Trả về danh sách format audio có sẵn, mỗi phần tử là dict:
    { 'format_id', 'ext', 'bitrate' }.
    Nếu info là playlist, lấy entry đầu tiên để liệt kê.
    """
    if 'formats' not in info and 'entries' in info:
        entries = info['entries'] or []
        info = entries[0] if entries else info

    fmts = [f for f in info['formats'] if f.get('vcodec') == 'none']
    fmts.sort(key=lambda f: (f.get('abr') or f.get('tbr') or 0), reverse=True)

    out = []
    for f in fmts:
        br = f.get('abr') or f.get('tbr') or 0
        out.append({
            'format_id': f['format_id'],
            'ext': f['ext'],
            'bitrate': br
        })
    return out

def download_media(url, mode):
    """
    Tải media theo mode:
      - 'audio'        → bestaudio
      - 'video_only'   → bestvideo[ext=mp4]
      - 'video_audio'  → bestvideo[ext=mp4]+bestaudio/best (merge mp4)
    Với playlist, sẽ zip toàn bộ thư mục con.
    Trả về đường dẫn file kết quả.
    """
    info = extract_info(url)
    is_playlist = info.get('_type') == 'playlist'

    # chuẩn bị temp dir
    tmp = tempfile.TemporaryDirectory()
    base = tmp.name

    # xác định thư mục lưu và outtmpl
    if is_playlist:
        raw = info.get('playlist_title') or info.get('title') or 'playlist'
        folder = os.path.join(base, sanitize(raw))
        os.makedirs(folder, exist_ok=True)
        outtmpl = os.path.join(folder, '%(playlist_index)s - %(title)s.%(ext)s')
        noplay = False
    else:
        folder = base
        outtmpl = os.path.join(folder, '%(title)s.%(ext)s')
        noplay = True

    # chọn format và merge
    if mode == 'audio':
        fmt, merge = 'bestaudio', False
    elif mode == 'video_only':
        fmt, merge = 'bestvideo[ext=mp4]', False
    elif mode == 'video_audio':
        fmt, merge = 'bestvideo[ext=mp4]+bestaudio/best', True
    else:
        raise ValueError("Invalid mode")

    opts = {
        'format': fmt,
        'outtmpl': outtmpl,
        'noplaylist': noplay
    }
    if merge:
        opts['merge_output_format'] = 'mp4'

    with YoutubeDL(opts) as ydl:
        ydl.download([url])

    # trả về file hoặc zip
    if not is_playlist:
        files = os.listdir(folder)
        if not files:
            raise FileNotFoundError("Không có file sau khi tải")
        return os.path.join(folder, files[0])

    zip_base = os.path.join(base, 'result')
    zip_path = shutil.make_archive(zip_base, 'zip', root_dir=folder)
    return zip_path

def extract_info(url):
    """Lấy metadata (skip download) để kiểm tra video/playlist."""
    try:
        with YoutubeDL({'skip_download': True}) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        raise RuntimeError(f"Lỗi khi lấy info: {e}") from e

# ----- END CORE ----- #

@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        url  = request.form.get('url','').strip()
        mode = request.form.get('mode')
        # bước 1: nếu chọn audio và chưa xác nhận download → show danh sách format
        if mode == 'audio' and 'download_audio' not in request.form:
            try:
                info  = extract_info(url)
                fmts  = list_audio_formats(info)
            except Exception as e:
                return f"Error: {e}", 500
            return render_template('audio_formats.html', url=url, fmts=fmts)

        # bước 2: thực download (audio/video/video+audio)
        try:
            result_path = download_media(url, mode)
            filename    = os.path.basename(result_path)
            return send_file(result_path, as_attachment=True, download_name=filename)
        except Exception as e:
            return f"Error khi tải: {e}", 500

    return render_template('index.html')


if __name__ == '__main__':
    # debug=True chỉ dùng khi dev local
    app.run(host='0.0.0.0', port=5000, debug=True)
