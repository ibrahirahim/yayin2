#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import time
import os
import requests
import re

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def print_colored(color, text):
    print(f"{color}{text}{Colors.NC}")

RTMP_URL = "rtmp://ssh101.bozztv.com:1935/ssh101"
STREAM_KEY = "filbox1"
rtmp_server = f"{RTMP_URL}/{STREAM_KEY}"

# Yeni M3U kaynağınız ve sol üst logo URL'niz tanımlandı
M3U_SOURCE = "https://raw.githubusercontent.com/ibrahirahim/yayin2/refs/heads/main/playlist.m3u"
LOGO_URL = "https://i.hizliresim.com/8dvubeu.png"

def is_termux():
    return 'TERMUX_VERSION' in os.environ or '/data/data/com.termux' in os.environ

def check_dependencies():
    try:
        import requests
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except:
        if is_termux():
            subprocess.run(["pkg", "install", "-y", "ffmpeg"], check=True)

def m3u_dan_linkleri_cek(m3u_url):
    try:
        if m3u_url.startswith('http'):
            response = requests.get(m3u_url, timeout=15)
            response.raise_for_status()
            m3u_icerik = response.text
        else:
            if not os.path.exists(m3u_url): return []
            with open(m3u_url, 'r', encoding='utf-8') as f: m3u_icerik = f.read()
        
        video_linkleri = []
        for satir in m3u_icerik.split('\n'):
            satir = satir.strip()
            if satir.startswith('http'):
                if any(uzanti in satir.lower() for uzanti in ['.mp4', '.m3u8', '.ts', '.mkv', '.avi', '.mov', '.flv']):
                    video_linkleri.append(satir)
                elif not satir.endswith('.m3u'):
                    video_linkleri.append(satir)
        return video_linkleri
    except:
        return []

def download_logo():
    try:
        if LOGO_URL.startswith('http'):
            response = requests.get(LOGO_URL, timeout=15)
            with open('logo.png', 'wb') as f: f.write(response.content)
            return True
        return os.path.exists(LOGO_URL)
    except:
        return False

def start_stream():
    video_index = 0
    while True:
        try:
            playlist = m3u_dan_linkleri_cek(M3U_SOURCE)
            if len(playlist) == 0 and os.path.exists('playlist.m3u'):
                playlist = m3u_dan_linkleri_cek('playlist.m3u')
                
            if len(playlist) == 0:
                print_colored(Colors.RED, "⚠️ Liste boş. 10 saniye sonra tekrar denenecek...")
                time.sleep(10)
                continue
            
            if video_index >= len(playlist):
                video_index = 0
                
            video_url = playlist[video_index]
            print_colored(Colors.GREEN, f"▶ [{video_index+1}/{len(playlist)}] Yayınlanıyor: {video_url}")
            
            # Logo sol üst köşe (overlay=20:20)
            if os.path.exists('logo.png'):
                logo_input = ['-i', 'logo.png']
                filter_str = '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[v0];[1:v]scale=200:-1[logo];[v0][logo]overlay=20:20[v]'
            else:
                logo_input = []
                filter_str = '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[v]'
                
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
            
            video_index = (video_index + 1) % len(playlist)
            time.sleep(2)
        except KeyboardInterrupt:
            break
        except Exception as e:
            time.sleep(5)

def main():
    check_dependencies()
    download_logo()
    start_stream()

if __name__ == "__main__":
    main()
