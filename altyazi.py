#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import time
import os
import re
import json
import requests
from urllib.parse import quote

# ===================== AYARLAR =====================
RTMP_URL = "rtmp://ssh101.bozztv.com:1935/ssh101"
STREAM_KEY = "altyazı"
RTMP_SERVER = f"{RTMP_URL}/{STREAM_KEY}"

# M3U ve Logo Bağlantılarınız
M3U_URL = "https://raw.githubusercontent.com/ibrahirahim/yayin2/refs/heads/main/altyazı.m3u"
LOGO_URL = "https://raw.githubusercontent.com/ibrahirahim/yayin/refs/heads/main/1786515032621.png"

GIST_ID = "34df90330e4b0daeed9a5b516c1c368d"
GH_TOKEN = os.getenv("GH_TOKEN", "")

STREAM_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def safe_url_fetch(url):
    """URL içindeki Türkçe/Özel karakterleri güvenli formata çevirir."""
    if "://" in url:
        protocol, rest = url.split("://", 1)
        domain_and_path = rest.split("/", 1)
        if len(domain_and_path) > 1:
            domain, path = domain_and_path
            safe_path = quote(path)
            return f"{protocol}://{domain}/{safe_path}"
    return url

def get_gist_state():
    if not GIST_ID:
        return 0, 0
    try:
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GH_TOKEN}"} if GH_TOKEN else {}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            files = res.json().get("files", {})
            if "state.json" in files:
                data = json.loads(files["state.json"]["content"])
                return data.get("last_index", 0), data.get("last_seconds", 0)
    except Exception as e:
        print(f"⚠️ Gist okuma hatası: {e}")
    return 0, 0

def update_gist_state(index, seconds):
    if not GIST_ID or not GH_TOKEN:
        return
    try:
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        payload = {"files": {"state.json": {"content": json.dumps({"last_index": int(index), "last_seconds": int(seconds)})}}}
        requests.patch(url, headers=headers, json=payload, timeout=5)
    except Exception as e:
        print(f"⚠️ Gist güncelleme hatası: {e}")

def get_m3u_playlist_direct(m3u_url):
    try:
        headers = {'User-Agent': STREAM_USER_AGENT}
        safe_m3u_url = safe_url_fetch(m3u_url)
        response = requests.get(safe_m3u_url, headers=headers, timeout=15)
        if response.status_code == 200:
            lines = response.text.splitlines()
            playlist = []
            pending_sub = None
            
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and line.startswith('http'):
                    clean_url = line.split('?')[0].lower()
                    if clean_url.endswith('.srt') or clean_url.endswith('.vtt'):
                        pending_sub = line
                    else:
                        playlist.append({
                            'video': line,
                            'subtitle': pending_sub
                        })
                        pending_sub = None
            return playlist
    except Exception as e:
        print(f"⚠️ M3U çekme hatası: {e}")
    return []

def vtt_to_srt(vtt_content):
    """VTT içeriğini tam uyumlu SRT yapısına çevirir."""
    lines = vtt_content.splitlines()
    srt_output = []
    sub_index = 1
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # WEBVTT başlıklarını veya boş satırları atla
        if not line or line.startswith('WEBVTT') or line.startswith('NOTE') or line.startswith('STYLE'):
            i += 1
            continue
            
        # Zaman damgası satırını bul (Örn: 00:01:20.000 --> 00:01:23.000)
        if '-->' in line:
            # Noktaları virgül yap (FFmpeg SRT kuralı)
            time_line = line.replace('.', ',')
            
            # Eksik saat formatı varsa düzelt (00:12,000 --> 00:15,000 yerine 00:00:12,000 yap)
            time_parts = time_line.split('-->')
            start_t = time_parts[0].strip()
            end_t = time_parts[1].strip().split()[0] # Ek VTT parametrelerini temizle
            
            if start_t.count(':') == 1:
                start_t = "00:" + start_t
            if end_t.count(':') == 1:
                end_t = "00:" + end_t
                
            formatted_time = f"{start_t} --> {end_t}"
            
            # Metin satırlarını topla
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                # VTT HTML taglarını temizle (<b>, <i>, <v Name> vb.)
                clean_text = re.sub(r'<[^>]+>', '', lines[i].strip())
                if clean_text:
                    text_lines.append(clean_text)
                i += 1
                
            if text_lines:
                srt_output.append(f"{sub_index}\n{formatted_time}\n" + "\n".join(text_lines) + "\n")
                sub_index += 1
        else:
            i += 1
            
    return "\n".join(srt_output)

def download_and_convert_subtitle(url, output_srt):
    try:
        headers = {'User-Agent': STREAM_USER_AGENT}
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200 and len(res.text) > 10:
            content = res.text
            
            # VTT ise tam SRT dönüşümü yap
            if "WEBVTT" in content or url.lower().endswith('.vtt'):
                srt_text = vtt_to_srt(content)
            else:
                srt_text = content
            
            if srt_text.strip():
                with open(output_srt, 'w', encoding='utf-8') as f:
                    f.write(srt_text)
                
                time.sleep(0.5)
                if os.path.exists(output_srt) and os.path.getsize(output_srt) > 0:
                    print(f"✅ Altyazı başarıyla indirildi ve dönüştürüldü ({os.path.getsize(output_srt)} bayt)")
                    return True
    except Exception as e:
        print(f"⚠️ Altyazı indirme hatası: {e}")
        
    if os.path.exists(output_srt):
        os.remove(output_srt)
    return False

def download_file(url, local_filename):
    try:
        headers = {'User-Agent': STREAM_USER_AGENT}
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200 and len(res.content) > 0:
            with open(local_filename, 'wb') as f:
                f.write(res.content)
            return True
    except Exception as e:
        print(f"⚠️ Dosya indirme hatası ({local_filename}): {e}")
    return False

def start_m3u_stream():
    download_file(LOGO_URL, 'logo.png')
    
    current_index, last_seconds = get_gist_state()
    error_count = 0

    while True:
        playlist = get_m3u_playlist_direct(M3U_URL)
        if not playlist:
            print("⚠️ M3U listesi boş veya çekilemedi! 10 saniye sonra tekrar deneniyor...")
            time.sleep(10)
            continue
            
        if current_index >= len(playlist):
            current_index = 0
            last_seconds = 0

        item = playlist[current_index]
        target_video_url = item['video']
        target_sub_url = item['subtitle']
        
        has_sub = False
        if target_sub_url:
            print(f"📥 Altyazı indiriliyor: {target_sub_url}")
            has_sub = download_and_convert_subtitle(target_sub_url, 'current_sub.srt')

        print("=" * 60)
        print(f"📺 SSH101 Canlı Film Yayını - Film #{current_index + 1}")
        print(f"🎬 Video   : {target_video_url}")
        print(f"💬 Altyazı : {'EVET (Aktif)' if has_sub else 'HAYIR (İndirilemedi)'}")
        print(f"⏱️ Başlangıç: {last_seconds} sn")
        print("=" * 60)

        has_logo = os.path.exists('logo.png') and os.path.getsize('logo.png') > 0

        filters = ['scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[base]']
        last_v_label = '[base]'

        # Altyazı sadece geçerli bir şekilde oluştuysa filtreye dahil edilir
        if has_sub and os.path.exists('current_sub.srt') and os.path.getsize('current_sub.srt') > 0:
            filters.append(f"{last_v_label}subtitles=filename='current_sub.srt':force_style='FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1'[subbed]")
            last_v_label = '[subbed]'

        if has_logo:
            filter_str = ";".join([
                filters[0],
                '[1:v]scale=-2:120[logo]'
            ] + filters[1:] + [
                f"{last_v_label}[logo]overlay=40:40[v]"
            ])
            logo_input = ['-i', 'logo.png']
        else:
            filter_str = ";".join(filters) + f";{last_v_label}copy[v]"
            logo_input = []

        headers_arg = f"User-Agent: {STREAM_USER_AGENT}\r\n"

        command = [
            'ffmpeg',
            '-headers', headers_arg,
            '-ss', str(last_seconds),
            '-re',
            '-i', target_video_url
        ] + logo_input + [
            '-filter_complex', filter_str,
            '-map', '[v]',
            '-map', '0:a?',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-pix_fmt', 'yuv420p',
            '-b:v', '1000k',
            '-maxrate', '1000k',
            '-bufsize', '2000k',
            '-g', '50',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '44100',
            '-f', 'flv',
            RTMP_SERVER
        ]

        process = subprocess.Popen(command, stderr=subprocess.PIPE, universal_newlines=True)

        last_save_time = time.time()
        current_stream_seconds = last_seconds
        ffmpeg_logs = []

        while True:
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
            
            if line:
                ffmpeg_logs.append(line)
                if len(ffmpeg_logs) > 20:
                    ffmpeg_logs.pop(0)

            if "time=" in line:
                time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
                if time_match:
                    hrs, mins, secs = time_match.groups()
                    played_seconds = int(hrs) * 3600 + int(mins) * 60 + float(secs)
                    current_stream_seconds = last_seconds + played_seconds
                    error_count = 0
                    
                    if time.time() - last_save_time > 15:
                        update_gist_state(current_index, current_stream_seconds)
                        last_save_time = time.time()

        if process.returncode == 0:
            current_index += 1
            last_seconds = 0
            update_gist_state(current_index, 0)
        else:
            print("❌ FFmpeg hatası oluştu! Son loglar:")
            print("".join(ffmpeg_logs[-10:]))
            error_count += 1
            
            if error_count >= 3:
                print("⚠️ Film 3 kez başlatılamadı, sonraki filme geçiliyor...")
                current_index += 1
                last_seconds = 0
                error_count = 0
            else:
                last_seconds = current_stream_seconds
            
            update_gist_state(current_index, last_seconds)

        if os.path.exists('current_sub.srt'):
            os.remove('current_sub.srt')

        time.sleep(5)

if __name__ == "__main__":
    start_m3u_stream()
