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
STREAM_KEY = "animasyon"
RTMP_SERVER = f"{RTMP_URL}/{STREAM_KEY}"

# M3U ve Logo artık yerel dosya yolundan okunuyor
M3U_PATH = "Planetç.m3u"
LOGO_PATH = "1787069704883.png.png"

GIST_ID = "34df90330e4b0daeed9a5b516c1c368d"
GH_TOKEN = os.getenv("GH_TOKEN", "")

STREAM_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def get_gist_state():
    """Gist'ten en son kalınan video indeksini ve saniyeyi okur."""
    if not GIST_ID:
        print("⚠️ GIST_ID tanımlı değil!")
        return 0, 0
    try:
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GH_TOKEN}"} if GH_TOKEN else {}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            files = res.json().get("files", {})
            if "state.json" in files:
                content = files["state.json"]["content"]
                data = json.loads(content)
                idx = data.get("last_index", 0)
                sec = data.get("last_seconds", 0)
                print(f"✅ Gist başarıyla okundu -> İndeks: {idx}, Saniye: {sec}")
                return idx, sec
        else:
            print(f"❌ Gist okuma başarısız! HTTP Durum Kodu: {res.status_code}")
    except Exception as e:
        print(f"⚠️ Gist okuma hatası: {e}")
    return 0, 0

def update_gist_state(index, seconds):
    """Gist üzerine güncel konumu kaydeder."""
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
                "state.json": {
                    "content": json.dumps({"last_index": int(index), "last_seconds": int(seconds)})
                }
            }
        }
        res = requests.patch(url, headers=headers, json=payload, timeout=5)
        if res.status_code == 200:
            print(f"💾 Konum Gist'e Kaydedildi -> İndeks: {index}, Saniye: {int(seconds)}")
        else:
            print(f"⚠️ Gist güncelleme hatası HTTP: {res.status_code}")
    except Exception as e:
        print(f"⚠️ Gist güncelleme hatası: {e}")

def get_m3u_playlist(m3u_path):
    """Yerel M3U dosyasındaki tüm yayın/dosya linklerini/yollarını çekip liste olarak döner."""
    try:
        if not os.path.exists(m3u_path):
            print(f"❌ M3U dosyası bulunamadı: {m3u_path}")
            return []
        with open(m3u_path, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
        playlist = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                playlist.append(line)
        return playlist
    except Exception as e:
        print(f"⚠️ M3U okuma hatası: {e}")
    return []

def check_logo():
    """Yerel logo dosyasının var olup olmadığını kontrol eder."""
    if os.path.exists(LOGO_PATH) and os.path.getsize(LOGO_PATH) > 0:
        print(f"✅ Logo dosyası bulundu: {LOGO_PATH}")
        return True
    print(f"⚠️ Logo dosyası bulunamadı: {LOGO_PATH}")
    return False

def start_m3u_stream():
    has_logo = check_logo()

    current_index, last_seconds = get_gist_state()

    while True:
        playlist = get_m3u_playlist(M3U_PATH)
        if not playlist:
            time.sleep(10)
            continue

        if current_index >= len(playlist):
            current_index = 0
            last_seconds = 0

        target_stream_url = playlist[current_index]

        print("=" * 60)
        print("📺 SSH101 Canlı M3U Aktarım Yayını (1080p 60fps - 2000k) Başlatılıyor")
        print(f"📡 Kaynak Dosya/Yol : {target_stream_url}")
        print(f"⏱️ Başlangıç Saniyesi: {last_seconds}")
        print(f"🚀 Hedef RTMP       : {RTMP_SERVER}")
        print("=" * 60)

        # 1080p 60FPS Logo ve Ölçeklendirme Filtresi
        if has_logo:
            filter_str = (
                '[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,'
                'pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,fps=60[main];'
                '[1:v]scale=-2:80[logo];'
                '[main][logo]overlay=55:55[v]'
            )
            logo_input = ['-i', LOGO_PATH]
        else:
            filter_str = (
                '[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,'
                'pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,fps=60[v]'
            )
            logo_input = []

        headers_arg = f"User-Agent: {STREAM_USER_AGENT}\r\n"

        # 1080p 60fps & 2000k Bitrate Parametreleri
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
            '-r', '60',              # Kare hızı 60 FPS
            '-b:v', '2000k',        # Video Bitrate (2000 kbps)
            '-maxrate', '2000k',    # Maksimum sıçrama sınırı
            '-bufsize', '4000k',    # Tampon boyutu
            '-g', '120',            # 60 fps için 2 saniyelik Keyframe aralığı (GOP)
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '44100',
            '-f', 'flv',
            RTMP_SERVER
        ]

        print("▶ FFmpeg başlatıldı, 1080p 60fps @ 2000k yayın iletiliyor...")

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
                time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
                if time_match:
                    hrs, mins, secs = time_match.groups()
                    played_seconds = int(hrs) * 3600 + int(mins) * 60 + float(secs)
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

        print("⚠️ Yayın durdu! 5 saniye sonra tekrar bağlanılıyor...")
        time.sleep(5)

if __name__ == "__main__":
    start_m3u_stream()
