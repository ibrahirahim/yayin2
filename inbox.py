#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import time
import os
import re
import json
import requests

# ===================== AYARLAR =====================
RTMP_URL = "rtmp://ssh101.bozztv.com:1935/ssh101"
STREAM_KEY = "inbox1"
RTMP_SERVER = f"{RTMP_URL}/{STREAM_KEY}"

CHANNEL_NAME = "kanal1"
STATE_FILE_NAME = f"state_{CHANNEL_NAME}.json"

M3U_FILE = "pars.m3u"
LOGO_FILE = "1787069925822.png"

GIST_ID = "34df90330e4b0daeed9a5b516c1c368d"
GH_TOKEN = os.getenv("GH_TOKEN", "")

STREAM_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"

def get_gist_state():
    """Gist'ten en son kalınan film indeksini ve saniyesini okur."""
    if not GIST_ID:
        return 0, 0
    try:
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GH_TOKEN}"} if GH_TOKEN else {}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            files = res.json().get("files", {})
            if STATE_FILE_NAME in files:
                content = files[STATE_FILE_NAME]["content"]
                data = json.loads(content)
                idx = int(data.get("last_index", 0))
                sec = int(data.get("last_seconds", 0))
                print(f"✅ Gist Okundu -> Film Sırası: {idx}, Kaldığı Saniye: {sec}")
                return idx, sec
            else:
                print(f"ℹ️ Gist içinde '{STATE_FILE_NAME}' dosyası henüz yok, baştan başlanıyor.")
        else:
            print(f"❌ Gist okunamadı! HTTP Kodu: {res.status_code}")
    except Exception as e:
        print(f"⚠️ Gist okuma hatası: {e}")
    return 0, 0

def update_gist_state(index, seconds):
    """Gist üzerine güncel konumu yazar."""
    if not GIST_ID or not GH_TOKEN:
        return
    try:
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {
            "Authorization": f"token {GH_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        payload = {
            "files": {
                STATE_FILE_NAME: {
                    "content": json.dumps({"last_index": int(index), "last_seconds": int(seconds)})
                }
            }
        }
        res = requests.patch(url, headers=headers, json=payload, timeout=5)
        if res.status_code == 200:
            print(f"💾 Gist Kaydedildi -> Film Sırası: {index}, Saniye: {int(seconds)}")
    except Exception as e:
        print(f"⚠️ Gist güncelleme hatası: {e}")

def get_m3u_playlist(m3u_file_path):
    """M3U dosyasını okuyarak film ve link listesini çıkarır."""
    try:
        if os.path.exists(m3u_file_path):
            with open(m3u_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            playlist = []
            current_title = "Film Yayini"
            for line in lines:
                line = line.strip()
                if line.startswith('#EXTINF:'):
                    if ',' in line:
                        current_title = line.split(',', 1)[1].strip()
                elif line and not line.startswith('#') and line.startswith('http'):
                    playlist.append((line, current_title))
                    current_title = "Film Yayini"
            return playlist
    except Exception as e:
        print(f"⚠️ M3U okuma hatası: {e}")
    return []

def check_logo():
    return os.path.exists(LOGO_FILE) and os.path.getsize(LOGO_FILE) > 0

def escape_ffmpeg_text(text):
    return text.replace(":", "\\:").replace("'", "").replace("%", "\\%")

def parse_ffmpeg_time(line):
    """FFmpeg logundaki süreyi tam saniyeye çevirir."""
    time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+|\d+)', line)
    if time_match:
        hrs, mins, secs = time_match.groups()
        return int(hrs) * 3600 + int(mins) * 60 + int(float(secs))
    return None

def start_m3u_stream():
    has_logo = check_logo()
    current_index, last_seconds = get_gist_state()

    while True:
        playlist = get_m3u_playlist(M3U_FILE)
        if not playlist:
            print("⚠️ Oynatma listesi boş! 10sn sonra tekrar denenecek...")
            time.sleep(10)
            continue
            
        # Liste sonuna gelindiyse başa dön
        if current_index >= len(playlist):
            current_index = 0
            last_seconds = 0

        target_stream_url, film_title = playlist[current_index]
        clean_title = escape_ffmpeg_text(film_title)
        
        print("=" * 60)
        print(f"🎬 Oynatılan Film : {film_title}")
        print(f"📊 Sıra/Toplam   : {current_index + 1} / {len(playlist)}")
        print(f"⏱️ Başlangıç Saniyesi: {last_seconds}")
        print("=" * 60)

        text_filter = (
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{clean_title}':fontsize=0:fontcolor=white:"
            f"x=w-tw-45:y=h-th-45"
        )

        if has_logo:
            filter_str = (
                '[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,'
                'pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[main];'
                '[1:v]scale=-2:80[logo];'
                '[main][logo]overlay=50:50[v_logo];'
                f'[v_logo]{text_filter}[v]'
            )
            logo_input = ['-i', LOGO_FILE]
        else:
            filter_str = (
                '[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,'
                'pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[v_base];'
                f'[v_base]{text_filter}[v]'
            )
            logo_input = []

        headers_arg = f"User-Agent: {STREAM_USER_AGENT}\r\n"

        # FFmpeg Komutu: Kaldığı saniyeden başlatmak için -ss -i'den önce olmalı!
        command = ['ffmpeg', '-headers', headers_arg]
        
        if last_seconds > 0:
            command.extend(['-ss', str(last_seconds)])

        command.extend([
            '-re',
            '-i', target_stream_url
        ])
        
        command.extend(logo_input)
        
        command.extend([
            '-filter_complex', filter_str,
            '-map', '[v]',
            '-map', '0:a?',
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-pix_fmt', 'yuv420p',
            '-b:v', '2000k',
            '-maxrate', '2000k',
            '-bufsize', '4000k',
            '-g', '50',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '44100',
            '-f', 'flv',
            RTMP_SERVER
        ])

        process = subprocess.Popen(
            command,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )

        last_save_time = time.time()
        current_stream_seconds = last_seconds

        while True:
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
            
            if "time=" in line:
                played_seconds = parse_ffmpeg_time(line)
                if played_seconds is not None:
                    # Başlangıç saniyesi + oynatılan saniye
                    current_stream_seconds = last_seconds + played_seconds
                    
                    # Her 15 saniyede bir Gist'e son konumu kaydet
                    if time.time() - last_save_time > 15:
                        update_gist_state(current_index, current_stream_seconds)
                        last_save_time = time.time()

        # Film bittiğinde veya kesildiğinde
        if process.returncode == 0:
            print("✅ Film normal şekilde tamamlandı. Bir sonraki filme geçiliyor...")
            current_index += 1
            last_seconds = 0
            update_gist_state(current_index, 0)
        else:
            print(f"⚠️ Yayın kesildi! Kaldığı saniye kaydediliyor: {current_stream_seconds}")
            last_seconds = current_stream_seconds
            update_gist_state(current_index, last_seconds)

        time.sleep(5)

if __name__ == "__main__":
    start_m3u_stream()
