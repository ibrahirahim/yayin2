import subprocess
import threading
import time
import os

# ===================== SSH101.com AYARLARI =====================
RTMP_URL = "rtmp://ssh101.bozztv.com:1935/ssh101"
STREAM_KEY = "fil2"
rtmp_server = f"{RTMP_URL}/{STREAM_KEY}"

# ===================== YAYIN AYARLARI =====================
PLAYLIST_FILE = "playlist.m3u"
LOGO_URL = "https://i.hizliresim.com/74c1k5c.png"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Playlist dosyasının kaç saniyede bir yeniden okunacağı
PLAYLIST_REFRESH_INTERVAL = 60

print("=" * 50)
print("📺 SSH101.com Yayın Başlatılıyor")
print("=" * 50)
print(f"🎨 Logo: {LOGO_URL}")
print(f"🔑 Stream Key: {STREAM_KEY}")
print(f"📡 RTMP: {rtmp_server}")
print("=" * 50)

# Logo'yu indir
subprocess.run(["wget", "-O", "logo.png", LOGO_URL])

# ===================== PAYLAŞILAN DURUM =====================
playlist_lock = threading.Lock()
current_playlist = []  # [{"title": "...", "url": "..."}, ...]
son_oynatilan_url = None


def playlist_oku(dosya_yolu):
    """
    M3U dosyasını okur. #EXTINF satırındaki film adını bir sonraki
    http linkiyle eşleştirip {"title": ..., "url": ...} sözlükleri
    şeklinde liste döner.
    """
    liste = []
    baslik = None
    try:
        with open(dosya_yolu, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    # Örnek satır: #EXTINF:-1,Film Adı Burada
                    if ',' in line:
                        baslik = line.split(',', 1)[1].strip()
                    else:
                        baslik = None
                elif line.startswith("http"):
                    if not baslik:
                        # EXTINF yoksa dosya adından türet
                        baslik = os.path.basename(line.split('?')[0]) or "Bilinmeyen Film"
                    liste.append({"title": baslik, "url": line})
                    baslik = None
    except Exception as e:
        print(f"❌ Playlist okuma hatası: {e}")
    return liste


def playlist_guncelleyici(dosya_yolu, interval=PLAYLIST_REFRESH_INTERVAL):
    global current_playlist
    while True:
        time.sleep(interval)
        try:
            yeni_liste = playlist_oku(dosya_yolu)
            if len(yeni_liste) > 0:
                with playlist_lock:
                    if yeni_liste != current_playlist:
                        current_playlist = yeni_liste
                        print(f"🔄 Playlist güncellendi! Yeni film sayısı: {len(yeni_liste)}")
        except Exception as e:
            print(f"❌ Playlist güncelleme hatası: {e}")


def siradaki_videoyu_sec(liste):
    """Son oynatılan URL'ye göre sıradaki {"title","url"} öğesini seçer."""
    global son_oynatilan_url

    urls = [item["url"] for item in liste]

    if son_oynatilan_url is None or son_oynatilan_url not in urls:
        return liste[0]

    idx = urls.index(son_oynatilan_url)
    return liste[(idx + 1) % len(liste)]


# İlk playlist yüklemesi
current_playlist = playlist_oku(PLAYLIST_FILE)

if len(current_playlist) == 0:
    raise Exception("playlist.m3u içinde video bulunamadı")

# Güncelleyici thread'i başlat
guncelleme_thread = threading.Thread(
    target=playlist_guncelleyici,
    args=(PLAYLIST_FILE, PLAYLIST_REFRESH_INTERVAL),
    daemon=True
)
guncelleme_thread.start()

# ===================== YAYIN DÖNGÜSÜ =====================
while True:
    with playlist_lock:
        liste = current_playlist.copy()

    if len(liste) == 0:
        print("⚠️ Playlist boş, 5 saniye sonra tekrar denenecek...")
        time.sleep(5)
        continue

    secilen = siradaki_videoyu_sec(liste)
    video = secilen["url"]
    baslik = secilen["title"]
    son_oynatilan_url = video

    # Film adını dosyaya yaz (ffmpeg drawtext bunu okuyacak)
    try:
        with open("title.txt", "w", encoding="utf-8") as f:
            f.write(baslik)
    except Exception as e:
        print(f"❌ Başlık dosyası yazma hatası: {e}")

    print(f"▶ Yayınlanıyor: {baslik}")
    print(f"   Kaynak: {video}")

    command = [
        'ffmpeg',
        '-re',
        '-i', video,
        '-i', 'logo.png',
        '-filter_complex',
        '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,'
        'pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[v0];'
        '[1:v]scale=200:-1[logo];'
        '[v0][logo]overlay=W-w-9:3[vlogo];'
        f'[vlogo]drawtext=fontfile={FONT_PATH}:'
        'textfile=title.txt:reload=1:'
        'fontcolor=white:fontsize=22:'
        'box=1:boxcolor=black@0.6:boxborderw=8:'
        'x=20:y=h-text_h-20[v]',
        '-map', '[v]',
        '-map', '0:a?',
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-pix_fmt', 'yuv420p',
        '-b:v', '4000k',
        '-maxrate', '4000k',
        '-bufsize', '8000k',
        '-g', '50',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-ar', '44100',
        '-f', 'flv',
        rtmp_server
    ]

    process = subprocess.Popen(command)
    process.wait()

    print("⏭ Video bitti, sıradaki videoya geçiliyor...\n")
