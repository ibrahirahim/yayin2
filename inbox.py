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

# Canlı M3U8 Ana Yayın Linki (401 Hatası Veren Chunklist Yerine Ana Kök Link)
M3U8_URL = "https://tv91.radyotelekom.com.tr:3466/stream/play.m3u8"

# Logo Bağlantısı (Raw Formatında)
LOGO_URL = "https://raw.githubusercontent.com/ibrahirahim/yayin2/main/1785481173165.png"

# IPTV Engeline Takılmamak İçin Gerçek Tarayıcı User-Agent'ı
STREAM_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REFERER_URL = "https://radyotelekomtv.com/"

def check_dependencies():
    """Gerekli kütüphane ve FFmpeg kontrolü yapar."""
    try:
        import requests  # noqa: F401
    except ImportError:
        print("📦 'requests' kütüphanesi yükleniyor...")
        subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except Exception:
        print("❌ HATA: FFmpeg sisteminizde kurulu değil! Lütfen FFmpeg kurup tekrar deneyin.")
        sys.exit(1)

def download_logo():
    """Logoyu indirir ve kaydeder."""
    try:
        headers = {'User-Agent': STREAM_USER_AGENT}
        response = requests.get(LOGO_URL, headers=headers, timeout=15)
        if response.status_code == 200 and len(response.content) > 0:
            with open('logo.png', 'wb') as f:
                f.write(response.content)
            print("✅ Logo başarıyla indirildi ve kaydedildi.")
        else:
            print(f"⚠️ Logo indirilemedi (HTTP {response.status_code}). Logosuz yayın yapılacak.")
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
            has_logo = os.path.exists('logo.png') and os.path.getsize('logo.png') > 0

            if has_logo:
                print("🖼️ Logo bulundu, overlay filtresi uygulanıyor...")
                filter_str = (
                    '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,'
                    'pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[main];'
                    '[1:v]scale=-1:50[logo];'
                    '[main][logo]overlay=W-w-10:10[v]'
                )
                logo_input = ['-i', 'logo.png']
            else:
                print("⚠️ Logo bulunamadı, logosuz yayın yapılıyor...")
                filter_str = (
                    '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,'
                    'pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[v]'
                )
                logo_input = []

            # 401 Unauthorized Hatasını Önlemek İçin Özel Başlıklar (Headers)
            headers_arg = f"User-Agent: {STREAM_USER_AGENT}\r\nReferer: {REFERER_URL}\r\n"

            command = [
                'ffmpeg',
                '-headers', headers_arg,
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
