#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import time
import os
import requests
import json
import signal

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def print_colored(color, text):
    print(f"{color}{text}{Colors.NC}")

RTMP_URL = "rtmp://ssh101.bozztv.com:1935/ssh101"
STREAM_KEY = "filmbox1"
rtmp_server = f"{RTMP_URL}/{STREAM_KEY}"

M3U_SOURCE = "https://raw.githubusercontent.com/ibrahirahim/yayin2/refs/heads/main/playlist.m3u"
LOGO_URL = "https://i.hizliresim.com/4ovbzg4.png"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def check_dependencies():
    """Gerekli bağımlılıkları kontrol et ve kur"""
    try:
        import requests
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    
    # FFmpeg kontrolü
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        print_colored(Colors.GREEN, "✅ FFmpeg hazır")
    except Exception as e:
        print_colored(Colors.RED, f"❌ FFmpeg bulunamadı: {e}")
        if os.path.exists('/data/data/com.termux'):
            subprocess.run(["pkg", "install", "-y", "ffmpeg"], check=True)
        else:
            print_colored(Colors.RED, "Lütfen FFmpeg'i yükleyin: sudo apt-get install ffmpeg")
            sys.exit(1)

def get_video_duration(video_url):
    """Video süresini al"""
    try:
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
               '-of', 'default=noprint_wrappers=1:nokey=1', video_url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        print_colored(Colors.YELLOW, f"⚠️ Süre alınamadı: {e}")
    return None

def m3u_dan_listeyi_cek(m3u_url):
    """M3U listesini çek"""
    try:
        print_colored(Colors.BLUE, f"📥 M3U çekiliyor: {m3u_url}")
        
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
        
        print_colored(Colors.GREEN, f"✅ {len(liste)} film bulundu")
        return liste
    except Exception as e:
        print_colored(Colors.RED, f"❌ M3U çekme hatası: {e}")
        return []

def download_logo():
    """Logo indir"""
    try:
        if LOGO_URL.startswith('http'):
            print_colored(Colors.BLUE, "📥 Logo indiriliyor...")
            response = requests.get(LOGO_URL, timeout=15)
            with open('logo.png', 'wb') as f:
                f.write(response.content)
            print_colored(Colors.GREEN, "✅ Logo indirildi")
            return True
        return os.path.exists(LOGO_URL)
    except Exception as e:
        print_colored(Colors.YELLOW, f"⚠️ Logo indirilemedi: {e}")
        return False

def test_video_url(video_url):
    """Video URL'sini test et"""
    try:
        print_colored(Colors.BLUE, f"🔍 Video test ediliyor: {video_url[:50]}...")
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=format_name', 
               '-of', 'default=noprint_wrappers=1:nokey=1', video_url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            print_colored(Colors.GREEN, f"✅ Video erişilebilir: {result.stdout.strip()}")
            return True
        else:
            print_colored(Colors.RED, f"❌ Video erişilemez: {result.stderr}")
            return False
    except Exception as e:
        print_colored(Colors.RED, f"❌ Video test hatası: {e}")
        return False

def start_stream():
    """Ana yayın döngüsü"""
    video_sayaci = 0
    onceki_liste_imzasi = None
    basarisiz_deneme = 0
    
    print_colored(Colors.GREEN, "="*50)
    print_colored(Colors.GREEN, "📺 SSH101.com Canlı Yayın Başlatılıyor...")
    print_colored(Colors.GREEN, "="*50)
    print_colored(Colors.BLUE, f"RTMP Sunucu: {RTMP_URL}")
    print_colored(Colors.BLUE, f"Stream Key: {STREAM_KEY}")
    print_colored(Colors.BLUE, "="*50)

    while True:
        try:
            # M3U listesini çek
            playlist = m3u_dan_listeyi_cek(M3U_SOURCE)
            
            if len(playlist) == 0:
                basarisiz_deneme += 1
                print_colored(Colors.RED, f"⚠️ Liste boş ({basarisiz_deneme}. deneme). 10 saniye sonra tekrar...")
                if basarisiz_deneme > 5:
                    print_colored(Colors.RED, "❌ Çok fazla başarısız deneme, çıkılıyor...")
                    break
                time.sleep(10)
                continue
            
            basarisiz_deneme = 0  # Sıfırla
            
            # Liste değişikliğini kontrol et
            guncel_imza = tuple(item["url"] for item in playlist)
            if onceki_liste_imzasi is not None and guncel_imza != onceki_liste_imzasi:
                print_colored(Colors.YELLOW, "🔄 Playlist değişikliği tespit edildi, baştan başlanıyor...")
                video_sayaci = 0
            onceki_liste_imzasi = guncel_imza
            
            # Sıradaki filmi seç
            secilen_idx = video_sayaci % len(playlist)
            secilen = playlist[secilen_idx]
            
            video_url = secilen["url"]
            baslik = secilen["title"]
            video_sayaci += 1
            
            print_colored(Colors.GREEN, f"\n▶ Sıradaki Film: {baslik}")
            print_colored(Colors.BLUE, f"   Sıra: {video_sayaci}/{len(playlist)}")
            
            # Video URL'sini test et
            if not test_video_url(video_url):
                print_colored(Colors.YELLOW, "⏭ Bu video atlanıyor, sıradaki deneniyor...")
                time.sleep(2)
                continue
            
            # Film süresini al
            duration = get_video_duration(video_url)
            duration_text = ""
            if duration:
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                duration_text = f"Toplam: {minutes:02d}:{seconds:02d}"
                print_colored(Colors.BLUE, f"   Süre: {duration_text}")
            else:
                duration_text = "Süre: Bilinmiyor"
            
            # Film bilgilerini dosyaya yaz
            try:
                with open("title.txt", "w", encoding="utf-8") as f:
                    f.write(f"{baslik}\n{duration_text}")
            except Exception as e:
                print_colored(Colors.YELLOW, f"⚠️ title.txt yazılamadı: {e}")
            
            # FFmpeg komutunu hazırla
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
                    'x=20:y=h-text_h-20,'
                    'drawtext=fontfile={FONT_PATH}:'
                    'text=%{{pts\\:hms}}:'
                    'fontcolor=yellow:fontsize=18:'
                    'x=20:y=h-text_h-50[v]'
                )
            else:
                logo_input = []
                filter_str = (
                    '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,'
                    'pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[v0];'
                    f'[v0]drawtext=fontfile={FONT_PATH}:'
                    'textfile=title.txt:reload=1:'
                    'fontcolor=white:fontsize=18:line_spacing=6:'
                    'x=20:y=h-text_h-20,'
                    'drawtext=fontfile={FONT_PATH}:'
                    'text=%{{pts\\:hms}}:'
                    'fontcolor=yellow:fontsize=18:'
                    'x=20:y=h-text_h-50[v]'
                )
            
            command = [
                'ffmpeg', '-re', '-i', video_url
            ] + logo_input + [
                '-filter_complex', filter_str,
                '-map', '[v]', '-map', '0:a?', 
                '-c:v', 'libx264', '-preset', 'veryfast',
                '-pix_fmt', 'yuv420p', 
                '-b:v', '2000k', '-maxrate', '2000k', '-bufsize', '4000k',
                '-g', '50', 
                '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', 
                '-f', 'flv', rtmp_server
            ]
            
            print_colored(Colors.BLUE, f"🚀 Yayın başlatılıyor...")
            print_colored(Colors.BLUE, f"   Komut: {' '.join(command[:3])} ...")
            
            # FFmpeg'i başlat
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Çıktıları izle
            while True:
                try:
                    # stdout ve stderr'den oku
                    stdout_line = process.stdout.readline()
                    stderr_line = process.stderr.readline()
                    
                    if stdout_line:
                        print_colored(Colors.BLUE, f"[FFmpeg] {stdout_line.strip()}")
                    
                    if stderr_line:
                        if "error" in stderr_line.lower() or "failed" in stderr_line.lower():
                            print_colored(Colors.RED, f"[FFmpeg HATA] {stderr_line.strip()}")
                        else:
                            print_colored(Colors.YELLOW, f"[FFmpeg] {stderr_line.strip()}")
                    
                    # Process bitti mi?
                    if process.poll() is not None:
                        break
                        
                except Exception as e:
                    print_colored(Colors.RED, f"⚠️ FFmpeg okuma hatası: {e}")
                    break
            
            # Process'in durumunu kontrol et
            if process.returncode != 0:
                print_colored(Colors.RED, f"❌ FFmpeg hatayla sonlandı (kod: {process.returncode})")
                stdout, stderr = process.communicate()
                if stderr:
                    print_colored(Colors.RED, f"Hata detayı: {stderr[:500]}")
            else:
                print_colored(Colors.GREEN, "✅ Video başarıyla tamamlandı")
            
            print_colored(Colors.YELLOW, "⏭ Sıradaki filme geçiliyor...\n")
            time.sleep(3)
            
        except KeyboardInterrupt:
            print_colored(Colors.RED, "\n⏹ Yayın durduruldu.")
            break
        except Exception as e:
            print_colored(Colors.RED, f"❌ Beklenmeyen hata: {e}")
            time.sleep(5)

def main():
    """Ana fonksiyon"""
    print_colored(Colors.GREEN, "="*50)
    print_colored(Colors.GREEN, "SSH101.com Canlı Yayın Sistemi")
    print_colored(Colors.GREEN, "="*50)
    
    # Bağımlılıkları kontrol et
    check_dependencies()
    
    # Logo indir
    download_logo()
    
    # Font kontrolü
    if not os.path.exists(FONT_PATH):
        print_colored(Colors.YELLOW, f"⚠️ Font bulunamadı: {FONT_PATH}")
        print_colored(Colors.YELLOW, "   Varsayılan font kullanılacak...")
        FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    
    # Yayını başlat
    start_stream()

if __name__ == "__main__":
    main()
