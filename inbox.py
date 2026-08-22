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

# Kanal Kimliği (Farklı scriptler için bu ismi değiştirebilirsiniz)
CHANNEL_NAME = "kanal1"
STATE_FILE_NAME = f"state_{CHANNEL_NAME}.json"

# Yerel M3U ve Logo Dosya Yolları
M3U_FILE = "pars.m3u"
LOGO_FILE = "1787069925822.png"

GIST_ID = "34df90330e4b0daeed9a5b516c1c368d"
GH_TOKEN = os.getenv("GH_TOKEN", "")

STREAM_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def get_gist_state():
    """Gist'ten ilgili kanala ait en son kalınan video indeksini ve saniyeyi okur."""
    if not GIST_ID:
        print("⚠️ GIST_ID tanımlı değil!")
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
                idx = data.get("last_index", 0)
                sec = data.get("last_seconds", 0)
                print(f"✅ Gist başarıyla okundu [{STATE_FILE_NAME}] -> İndeks: {idx}, Saniye: {sec}")
                return idx, sec
            else:
                print(f"ℹ️ Gist içinde '{STATE_FILE_NAME}' henüz yok. Baştan (0,0) başlanıyor...")
        else:
            print(f"❌ Gist okuma başarısız! HTTP Durum Kodu: {res.status_code}")
    except Exception as e:
        print(f"⚠️ Gist okuma hatası: {e}")
    return 0, 0

def update_gist_state(index, seconds):
    """Gist üzerinde ilgili kanala ait dosyaya güncel konumu kaydeder."""
    if not GIST_ID or not GH_TOKEN:
        print("⚠️ GIST_ID veya GH_TOKEN eksik, Gist güncellenemiyor!")
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
            print(f"💾 Konum Gist'e Kaydedildi [{STATE_FILE_NAME}] -> İndeks: {index}, Saniye: {int(seconds)}")
        else:
            print(f"⚠️ Gist güncelleme hatası HTTP: {res.status_code}")
    except Exception as e:
        print(f"⚠️ Gist güncelleme hatası: {e}")

def get_m3u_playlist(m3u_file_path):
    """Yerel M3U dosyasını okur."""
    try:
        if os.path.exists(m3u_file_path):
            with open(m3u_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            playlist = []
            current_title = "Canli Yayin"
            
            for line in lines:
                line = line.strip()
                if line.startswith('#EXTINF:'):
                    if ',' in line:
                        current_title = line.split(',', 1)[1].strip()
                elif line and not line.startswith('#') and line.startswith('http'):
                    playlist.append((line, current_title))
                    current_title = "Canli Yayin"
            
            if playlist:
                return playlist
        else:
            print(f"⚠️ M3U dosyası bulunamadı: {m3u_file_path}")
    except Exception as e:
        print(f"⚠️ M3U dosyası okuma hatası: {e}")
    return []

def check_logo():
    """Yerel logo dosyasının varlığını kontrol eder."""
    if os.path.exists(LOGO_FILE) and os.path.getsize(LOGO_FILE) > 0:
        print(f"✅ Logo dosyası doğrulandı: {LOGO_FILE}")
        return True
    else:
        print(f"⚠️ Logo dosyası bulunamadı veya boş: {LOGO_FILE}")
        return False

def escape_ffmpeg_text(text):
    text = text.replace(":", "\\:").replace("'", "").replace("%", "\\%")
    return text

def parse_ffmpeg_time(line):
    """FFmpeg loglarındaki zamanı her türlü formatta saniyeye çevirir."""
    time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+|\d+)', line)
    if time_match:
        hrs, mins, secs = time_match.groups()
        return int(hrs) * 3600 + int(mins) * 60 + float(secs)
    
    sec_match = re.search(r'time=(\d+\.\d+|\d+)', line)
    if sec_match:
        return float(sec_match.group(1))
        
    return None

def start_m3u_stream():
    has_logo = check_logo()
    current_index, last_seconds = get_gist_state()

    while True:
        playlist = get_m3u_playlist(M3U_FILE)
        if not playlist:
            print("⚠️ Oynatma listesi boş veya okunamadı! 10 saniye sonra tekrar denenecek...")
            time.sleep(10)
            continue
            
        if current_index >= len(playlist):
            current_index = 0
            last_seconds = 0

        target_stream_url, film_title = playlist[current_index]
        clean_title = escape_ffmpeg_text(film_title)
        
        print("=" * 60)
        print(f"📺 SSH101 Canlı M3U Aktarım Yayını Başlatılıyor - Kanal: {CHANNEL_NAME} (1080p - 2000k)")
        print(f"🎬 Film / Yayın Adı : {film_title}")
        print(f"📊 Toplam Film Sayısı: {len(playlist)} (Mevcut Sıra: {current_index + 1})")
        print(f"📡 Kaynak Yayın     : {target_stream_url}")
        print(f"⏱️ Başlangıç Saniyesi: {last_seconds}")
        print(f"🚀 Hedef RTMP       : {RTMP_SERVER}")
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

        command = [
            'ffmpeg',
            '-headers', headers_arg,
            '-ss', str(last_seconds),
            '-re',
            '-i', target_stream_url
        ] + logo_input + [
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
        ]

        print("▶ FFmpeg başlatıldı, canlı yayın iletiliyor...")
        
        process = subprocess.Popen(
            command,
            stderr=subprocess.PIPE,
            universal_newlines=True
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
                    current_stream_seconds = last_seconds + played_seconds
                    
                    if time.time() - last_save_time > 15:
                        update_gist_state(current_index, current_stream_seconds)
                        last_save_time = time.time()

        if process.returncode == 0:
            current_index += 1
            last_seconds = 0
            update_gist_state(current_index, 0)
        else:
            last_seconds = current_stream_seconds
            update_gist_state(current_index, last_seconds)

        print("⚠️ Yayın tamamlandı / kesildi! 5 saniye sonra yenilenen liste ile devam ediliyor...")
        time.sleep(5)

if __name__ == "__main__":
    start_m3u_stream()
