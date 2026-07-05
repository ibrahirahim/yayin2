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

# Playlist dosyasının kaç saniyede bir yeniden okunacağı
PLAYLIST_REFRESH_INTERVAL = 60  # GitHub Actions checkout ile senkron çalışıyorsa 60 sn yeterli

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
current_playlist = []
son_oynatilan_url = None


def playlist_oku(dosya_yolu):
    liste = []
    try:
        with open(dosya_yolu, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("http"):
                    liste.append(line)
    except Exception as e:
        print(f"❌ Playlist okuma hatası: {e}")
    return liste


def playlist_guncelleyici(dosya_yolu, interval=PLAYLIST_REFRESH_INTERVAL):
    """Arka planda periyodik olarak playlist.m3u dosyasını yeniden okur.
    Not: GitHub Actions ortamında bu dosyanın canlı güncellenmesi için
    workflow'un ayrıca dosyayı yeniden çekmesi/senkronlaması gerekir
    (aşağıdaki workflow.yml örneğine bakın)."""
    global current_playlist

    while True:
        time.sleep(interval)
        try:
            yeni_liste = playlist_oku(dosya_yolu)
            if len(yeni_liste) > 0:
                with playlist_lock:
                    if yeni_liste != current_playlist:
                        current_playlist = yeni_liste
                        print(f"🔄 Playlist güncellendi! Yeni video sayısı: {len(yeni_liste)}")
        except Exception as e:
            print(f"❌ Playlist güncelleme hatası: {e}")


def siradaki_videoyu_sec(liste):
    global son_oynatilan_url

    if son_oynatilan_url is None:
        return liste[0]

    if son_oynatilan_url in liste:
        idx = liste.index(son_oynatilan_url)
        return liste[(idx + 1) % len(liste)]

    return liste[0]


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

    video = siradaki_videoyu_sec(liste)
    son_oynatilan_url = video

    print(f"▶ Yayınlanıyor: {video}")

    command = [
        'ffmpeg',
        '-re',
        '-i', video,
        '-i', 'logo.png',
        '-filter_complex',
        '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,'
        'pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[v0];'
        '[1:v]scale=200:-1[logo];'
        '[v0][logo]overlay=W-w-9:3,'
        "drawtext=text='':"
        "fontcolor=white:"
        "fontsize=24:"
        "box=1:"
        "boxcolor=black@0.6:"
        "boxborderw=5:"
        "x=(w-text_w)/2:"
        "y=h-text_h-20[v]",
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
