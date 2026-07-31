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

# Canlı M3U8 Yayın Linki
M3U8_URL = "https://radyotelekomtv.com/player/m3u8/333a006f25068d7fde195a4f0c988474/chunklist_w220756748.m3u8"

# Logo Bağlantısı (Raw Formatında)
LOGO_URL = "https://raw.githubusercontent.com/ibrahirahim/yayin2/main/1785481173165.png"

# IPTV Engeline Takılmamak İçin User-Agent
STREAM_USER_AGENT = "VLC/3.0.18 LibVLC/3.0.18"

def check_dependencies():
    """Gerekli kütüphane ve FFmpeg kontrolü yapar."""
    try:
        import requests  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except Exception:
        print("❌ HATA: FFmpeg sisteminizde kurulu değil! Lütfen FFmpeg kurup tekrar deneyin.")
        sys.exit(1)

def download_logo():
    """Logoyu indirir ve gerçek PNG resmi olduğunu doğrular."""
    try:
        response = requests.get(LOGO_URL, timeout=15)
        if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
            with open('logo.png', 'wb') as f:
                f.write(response.content)
            print("✅ Logo başarıyla indirildi.")
        else:
            print("⚠️ Logo linkinden geçerli bir resim alınamadı. Yayın logosuz devam edecek.")
    except Exception as e:
        print(f"⚠️ Logo indirme hatası: {e}. Yayın logosuz devam edecek.")

def start_m3u8_stream():
    """M3U8 yayınını alıp SSH101 RTMP sunucusuna canlı aktarır."""
    print("=" * 60)
    print("📺 SSH101 Canlı M3U8 Aktarım Yayını Başlatılıyor")
    print(f"📡 Kaynak M3U8 : {M3U8_URL}")
    print(f"🚀 Hedef RTMP  : {RTMP_SERVER}")
    print("=" * 60)

    while True:
        try:
            has_logo = os.path.exists('logo.png')

            if has_logo:
                # scale=-1:50 ile logo yüksekliği 50px olarak küçültüldü (orijinali 90px idi)
                filter_str = (
                    '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,'
                    'pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[v0];'
                    '[1:v]scale=-1:50[logo];'
                    '[v0][logo]overlay=W-w-10:10[v]'
                )
                logo_input = ['-i', 'logo.png']
            else:
                filter_str = (
                    '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,'
                    'pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[v]'
                )
                logo_input = []

            command = [
                'ffmpeg',
                '-user_agent', STREAM_USER_AGENT,
                '-re',
                '-i', M3U8_URL
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

            print("⚠️ Canlı yayın koptu veya durdu! 5 saniye sonra otomatik tekrar bağlanılacak...")
            time.sleep(5)

        except KeyboardInterrupt:
            print("\n🛑 Yayın kullanıcı tarafından durduruldu.")
            break
        except Exception as e:
            print(f"❌ Beklenmeyen hata: {e}")
            time.sleep(5)

def main():
    check_dependencies()
    download_logo()
    start_m3u8_stream()

if __name__ == "__main__":
    main()
