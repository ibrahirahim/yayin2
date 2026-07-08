#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import time
import os
import threading
import requests

class Colors:
    RED = '\033;31m'
    GREEN = '\033;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033;34m'
    NC = '\033[0m'

def print_colored(color, text):
    print(f"{color}{text}{Colors.NC}")

RTMP_URL = "rtmp://ssh101.bozztv.com:1935/ssh101"
STREAM_KEY = "tvgo1"
rtmp_server = f"{RTMP_URL}/{STREAM_KEY}"

# Buraya doğrudan oynatmak istediğiniz tekil m3u8 linkini yazın
M3U_SOURCE = "https://catcast.ismailturret.workers.dev/playercinema-premium5.m3u8"
STREAM_TITLE = ""  # Ekranda görünecek varsayılan yayın adı

LOGO_URL = "https://i.hizliresim.com/bxgiz3t.png"
# GitHub Actions (Ubuntu) varsayılan font yolu güncellendi
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def check_dependencies():
    try:
        import requests  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    
    # GitHub Actions ortamında fontun yüklü olduğundan emin olalım
    if not os.path.exists(FONT_PATH):
        print_colored(Colors.YELLOW, "⏳ Font dosyası aranıyor/kuruluyor...")
        subprocess.run(["sudo", "apt-get", "update"], capture_output=True)
        subprocess.run(["sudo", "apt-get", "install", "-y", "fonts-dejavu-core"], capture_output=True)

def download_logo():
    try:
        if LOGO_URL.startswith('http'):
            response = requests.get(LOGO_URL, timeout=15)
            with open('logo.png', 'wb') as f:
                f.write(response.content)
            return True
        return os.path.exists(LOGO_URL)
    except Exception:
        return False

def video_suresini_al(url):
    """ffprobe ile m3u8 video dosyasının süresini öğrenir. Canlı yayınsa None döner."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", url],
            capture_output=True, text=True, timeout=20
        )
        sure = float(result.stdout.strip())
        if sure > 0:
            return sure
    except Exception:
        pass
    return None

def sure_formatla(saniye):
    saniye = max(0, int(saniye))
    saat = saniye // 3600
    dakika = (saniye % 3600) // 60
    san = saniye % 60
    if saat > 0:
        return f"{saat:02d}:{dakika:02d}:{san:02d}"
    return f"{dakika:02d}:{san:02d}"

def sure_guncelleyici(baslik, toplam_sure, baslangic, durdur_event):
    while not durdur_event.is_set():
        try:
            if toplam_sure and toplam_sure > 0:
                kalan = toplam_sure - (time.time() - baslangic)
                metin = f"{baslik}\nKalan: {sure_formatla(kalan)}"
            else:
                metin = baslik
            with open("title.txt", "w", encoding="utf-8") as f:
                f.write(metin)
        except Exception:
            pass
        durdur_event.wait(1)

def start_stream():
    while True:
        try:
            print_colored(Colors.GREEN, f"▶ Yayınlanıyor: {STREAM_TITLE}")
            print_colored(Colors.BLUE, f"   Kaynak: {M3U_SOURCE}")

            toplam_sure = video_suresini_al(M3U_SOURCE)
            if toplam_sure:
                print_colored(Colors.BLUE, f"   Süre: {sure_formatla(toplam_sure)}")
            else:
                print_colored(Colors.YELLOW, "   Süre: Canlı Yayın / Belirsiz")

            durdur_event = threading.Event()
            guncelleyici = threading.Thread(
                target=sure_guncelleyici,
                args=(STREAM_TITLE, toplam_sure, time.time(), durdur_event),
                daemon=True
            )
            guncelleyici.start()

            if os.path.exists('logo.png'):
                logo_input = ['-i', 'logo.png']
                filter_str = (
                    '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,'
                    'pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[v0];'
                    '[1:v]scale=230:90[logo];'
                    '[v0][logo]overlay=W-w-10:10[vlogo];'
                    f'[vlogo]drawtext=fontfile={FONT_PATH}:'
                    'textfile=title.txt:reload=1:'
                    'fontcolor=white:fontsize=16:line_spacing=6:'
                    'x=23:y=h-text_h-20[v]'
                )
            else:
                logo_input = []
                filter_str = (
                    '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,'
                    'pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[v0];'
                    f'[v0]drawtext=fontfile={FONT_PATH}:'
                    'textfile=title.txt:reload=1:'
                    'fontcolor=white:fontsize=18:line_spacing=6:'
                    'x=20:y=h-text_h-20[v]'
                )

            # Canlı m3u8 akışları için -re (realtime) parametresi bazen takılma yapabilir.
            # Eğer yayın donarsa komuttaki '-re' parametresini kaldırıp deneyebilirsiniz.
            command = [
                'ffmpeg', '-re', '-i', M3U_SOURCE
            ] + logo_input + [
                '-filter_complex', filter_str,
                '-map', '[v]', '-map', '0:a?', '-c:v', 'libx264', '-preset', 'veryfast',
                '-pix_fmt', 'yuv420p', '-b:v', '4000k', '-maxrate', '4000k', '-bufsize', '8000k',
                '-g', '50', '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-f', 'flv', rtmp_server
            ]

            process = subprocess.Popen(command)
            process.wait()

            durdur_event.set()
            guncelleyici.join(timeout=2)

            print_colored(Colors.YELLOW, "🔄 Yayın kesildi veya bitti, 5 saniye sonra yeniden bağlanıyor...")
            time.sleep(5)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print_colored(Colors.RED, f"❌ Hata: {e}")
            time.sleep(5)

def main():
    check_dependencies()
    download_logo()
    start_stream()

if __name__ == "__main__":
    main()
