import subprocess
import time

# ===================== RTMP AYARLARI =====================
RTMP_URL = "rtmp://ssh101.bozztv.com:1935/ssh10"
STREAM_KEY = "deneme¹"
rtmp_server = f"{RTMP_URL}/{STREAM_KEY}"

# ===================== YAYIN AYARLARI =====================
VIDEO_URL = "http://3305.xtptr.com:80/live/isik7192/gueuncu/18.m3u8"   # kendi kameranız / sunucunuz / lisanslı akış
LOGO_URL = "https://i.hizliresim.com/bxgiz3t.png"

print("=" * 50)
print("📺 Yayın Başlatılıyor")
print(f"🎬 Video: {VIDEO_URL}")
print(f"📡 RTMP: {rtmp_server}")
print("=" * 50)

command = [
    'ffmpeg',
    '-re',
    '-stream_loop', '-1',
    '-i', VIDEO_URL,
    '-i', LOGO_URL,
    '-filter_complex',
    '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[v0];'
    '[1:v]scale=230:90[logo];'
    '[v0][logo]overlay=W-w-10:3[v1];'
    "[v1]drawtext=text='%{localtime\\:%H\\\\:%M\\\\:%S}':fontcolor=white:fontsize=28:box=1:boxcolor=black@0.6:boxborderw=5:x=20:y=h-th-20[v]",
    '-map', '[v]',
    '-map', '0:a?',
    '-c:v', 'libx264',
    '-preset', 'veryfast',
    '-b:v', '4000k',
    '-c:a', 'aac',
    '-b:a', '128k',
    '-f', 'flv',
    rtmp_server
]

print("\n🎥 Yayın başlatılıyor... (Durdurmak için Ctrl+C)\n")

try:
    proc = subprocess.Popen(command)
    while True:
        time.sleep(60)
        if proc.poll() is not None:
            print("⚠️ Yayın durdu, yeniden başlatılıyor...")
            proc = subprocess.Popen(command)
except KeyboardInterrupt:
    print("\n⛔ Yayın durduruluyor...")
    proc.terminate()
    print("✅ Yayın sonlandırıldı.")
