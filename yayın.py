#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import time
import os
import requests

class Colors:
    RED = '\033;31m'
    GREEN = '\033;32m'
    YELLOW = '\033;33m'
    BLUE = '\033;34m'
    NC = '\033[0m'

def print_colored(color, text):
    print(f"{color}{text}{Colors.NC}")

# ===================== SSH101.com AYARLARI =====================
RTMP_URL = "rtmp://ssh101.bozztv.com:1935/ssh101"
STREAM_KEY = "fil2"
rtmp_server = f"{RTMP_URL}/{STREAM_KEY}"

# ===================== YAYIN AYARLARI =====================
M3U_SOURCE = "https://raw.githubusercontent.com/ibrahirahim/yayin2/refs/heads/main/playlist.m3u"
PLAYLIST_FILE = "playlist.m3u"
LOGO_URL = "https://i.hizliresim.com/4ovbzg4.png"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def is_termux():
    return 'TERMUX_VERSION' in os.environ or '/data/data/com.termux' in os.environ

def check_dependencies():
    try:
        import requests  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except Exception:
        if is_termux():
            subprocess.run(["pkg", "install", "-y", "ffmpeg"], check=True)

def m3u_dan_listeyi_cek(m3u_url):
    try:
        if m3u_url.startswith('http'):
            cache_buster = f"?t={int(time.time())}"
            response = requests.get(m3u_url + cache_buster, timeout=15,
                                     headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
            response.raise_for_status()
            m3u_icerik = response.text
        else:
            if not os.path.exists(m3u_url):
                return []
            with open(m3u_url, 'r', encoding='utf-8') as f:
                m3u_icerik = f.read()

        liste = []
        baslik = None
        for satir in m3u_icerik.split('\n'):
            satir = satir.strip()
            if satir.startswith('#EXTINF'):
                if ',' in satir:
                    baslik = satir.split(',', 1)[1].strip()
                else:
                    baslik = None
            elif satir.startswith('http'):
                if not baslik:
                    baslik = os.path.basename(satir.split('?')[0]) or "Bilinmeyen Film"
                liste.append({"title": baslik, "url": satir})
                baslik = None
        return liste
    except Exception as e:
        print_colored(Colors.RED, f"❌ M3U çekme hatası: {e}")
        return []

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

def start_stream():
    # Sıra sayacı döngünün dışında başlar, böylece liste güncellense de sırasını kaybetmez
    stream_index = 0

    print("=" * 50)
    print("📺 SSH101.com Kesintisiz Canlı Yayın Başlatıldı")
    print("=" * 50)

    while True:
        try:
            playlist = m3u_dan_listeyi_cek(M3U_SOURCE)
            if len(playlist) == 0 and os.path.exists(PLAYLIST_FILE):
                playlist = m3u_dan_listeyi_cek(PLAYLIST_FILE)

            if len(playlist) == 0:
                print_colored(Colors.RED, "⚠️ Liste boş. 10 saniye sonra tekrar denenecek...")
                time.sleep(10)
                continue

            # Eğer liste güncellenirken küçüldüyse ve sayaç liste dışı kaldıysa başa sar
            if stream_index >= len(playlist):
                stream_index = 0

            secilen = playlist[stream_index]
            sonraki = playlist[(stream_index + 1) % len(playlist)]

            video_url = secilen["url"]
            baslik = secilen["title"]
            sonraki_baslik = sonraki["title"]

            # Ekrana yazdırılacak başlık dosyası oluşturuluyor
            try:
                with open("title.txt", "w", encoding="utf-8") as f:
                    f.write(f"Simdi: {baslik}\nSirada: {sonraki_baslik}")
            except Exception:
                pass

            print_colored(Colors.GREEN, f"▶ Yayinlaniyor [{stream_index + 1}/{len(playlist)}]: {baslik}")
            print_colored(Colors.BLUE, f"   Kaynak: {video_url}")

            # FFmpeg Logosu ve Filtre Ayarları
            if os.path.exists('logo.png'):
                logo_input = ['-i', 'logo.png']
                filter_str = (
                    '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,'
                    'pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[v0];'
                    '[1:v]scale=-1:90[logo];'
                    '[v0][logo]overlay=W-w-10:10[vlogo];'
                    f'[vlogo]drawtext=fontfile={FONT_PATH}:'
                    'textfile=title.txt:reload=1:'
                    'fontcolor=white:fontsize=18:line_spacing=6:'
                    'x=20:y=h-text_h-20[v]'
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

            command = [
                'ffmpeg', '-re', '-i', video_url
            ] + logo_input + [
                '-filter_complex', filter_str,
                '-map', '[v]', '-map', '0:a?', '-c:v', 'libx264', '-preset', 'veryfast',
                '-pix_fmt', 'yuv420p', '-b:v', '4000k', '-maxrate', '4000k', '-bufsize', '8000k',
                '-g', '50', '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-f', 'flv', rtmp_server
            ]

            process = subprocess.Popen(command)
            process.wait()

            # Video başarıyla bittiğinde bir sonraki sıraya geçiş yapıyoruz
            stream_index = (stream_index + 1) % len(playlist)
            print_colored(Colors.YELLOW, "⏭ Video bitti. Sira sayaci artirildi, siradaki videoya geciliyor...\n")
            time.sleep(2)

        except KeyboardInterrupt:
            print_colored(Colors.RED, "\n🛑 Yayin kullanıcı tarafından durduruldu.")
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
