#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import time
import os
import requests

# ===================== AYARLAR =====================
RTMP_URL = "rtmp://ssh101.bozztv.com:1935/ssh101"
STREAM_KEY = "inbox1"
RTMP_SERVER = f"{RTMP_URL}/{STREAM_KEY}"

# M3U Playlist Linki
M3U_URL = "https://raw.githubusercontent.com/ibrahirahim/yayin2/refs/heads/main/yerli.m3u"

# Yeni Logo Bağlantısı (Raw Formatında)
LOGO_URL = "https://raw.githubusercontent.com/ibrahirahim/yayin/main/1786025536044.png"

STREAM_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def check_dependencies():
    """Gerekli paketlerin kontrolü."""
    try:
        import requests  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except Exception:
        print("❌ HATA: FFmpeg yüklenemedi!")
        sys.exit(1)

def get_stream_url_from_m3u(m3u_url):
    """M3U listesini parse ederek yayın URL'sini alır."""
    try:
        headers = {'User-Agent': STREAM_USER_AGENT}
        response = requests.get(m3u_url, headers=headers, timeout=15)
        if response.status_code == 200:
            lines = response.text.splitlines()
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and line.startswith('http'):
                    print(f"✅ M3U içinden kanal linki çekildi: {line}")
                    return line
            return m3u_url
        else:
            print(f"⚠️ M3U indirilemedi (HTTP {response.status_code}).")
            return m3u_url
    except Exception as e:
        print(f"⚠️ M3U parse hatası: {e}")
        return m3u_url

def download_logo():
    """Logoyu indirir ve kaydeder."""
    try:
        headers = {'User-Agent': STREAM_USER_AGENT}
        response = requests.get(LOGO_URL, headers=headers, timeout=15)
        if response.status_code == 200 and len(response.content) > 0:
            with open('logo.png', 'wb') as f:
                f.write(response.content)
            print("✅ Logo başarıyla indirildi.")
        else:
            print("⚠️ Logo indirilemedi. Logosuz yayın yapılacak.")
    except Exception as e:
        print(f"⚠️ Logo indirme hatası: {e}")

def start_m3u_stream():
    """Yayın döngüsü."""
    check_dependencies()
    download_logo()
    
    while True:
        target_stream_url = get_stream_url_from_m3u(M3U_URL)
        
        print("=" * 60)
        print("📺 SSH101 Canlı M3U Aktarım Yayını Başlatılıyor")
        print(f"📡 Kaynak Yayın : {target_stream_url}")
        print(f"🚀 Hedef RTMP   : {RTMP_SERVER}")
        print("=" * 60)

        has_logo = os.path.exists('logo.png') and os.path.getsize('logo.png') > 0

        # Logo boyutu scale=-2:45 ile ideal ölçüye getirildi.
        # overlay=W-w-25:25 ile sağ ve üst kenarlardan biraz daha içeri çekildi.
        if has_logo:
            filter_str = (
                '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,'
                'pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[main];'
                '[1:v]scale=-2:45[logo];'
                '[main][logo]overlay=W-w-25:25[v]'
            )
            logo_input = ['-i', 'logo.png']
        else:
            filter_str = (
                '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,'
                'pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[v]'
            )
            logo_input = []

        headers_arg = f"User-Agent: {STREAM_USER_AGENT}\r\n"

        command = [
            'ffmpeg',
            '-headers', headers_arg,
            '-re',
            '-i', target_stream_url
        ] + logo_input + [
            '-filter_complex', filter_str,
            '-map', '[v]',
            '-map', '0:a?',
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-pix_fmt', 'yuv420p',
            '-b:v', '3000k',
            '-maxrate', '3000k',
            '-bufsize', '6000k',
            '-g', '50',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '44100',
            '-f', 'flv',
            RTMP_SERVER
        ]

        print("▶ FFmpeg başlatıldı, canlı yayın iletiliyor...")
        process = subprocess.Popen(command)
        process.wait()

        print("⚠️ Yayın koptu! 5 saniye sonra tekrar bağlanılıyor...")
        time.sleep(5)

if __name__ == "__main__":
    start_m3u_stream()
