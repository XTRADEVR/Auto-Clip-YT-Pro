import streamlit as st
import os
import subprocess
import uuid
import re

st.set_page_config(page_title="AutoClip PRO", page_icon="👑")
st.title("👑 AutoClip PRO - YT / TikTok")
st.write("Paste link ATAU Upload video -> Auto cari momen rame -> Auto caption -> Auto hook.")

# --- PILIH MODE ---
mode = st.radio("Pilih cara masukin video:", ["🔗 Paste Link", "📁 Upload Video dari HP"], horizontal=True)

url = ""
uploaded_file = None
if mode == "🔗 Paste Link":
    url = st.text_input("Paste Link YT / TikTok", placeholder="https://...")
else:
    uploaded_file = st.file_uploader("Upload video MP4 dari HP", type=["mp4", "mov", "mkv", "webm"])
    st.caption("Cara: Download dulu video TikTok pake SnapTik / ssstik, terus upload ke sini.")

clip_duration = st.slider("Durasi clip", 15, 60, 30)
max_clips = st.slider("Jumlah clip", 1, 5, 3)

st.divider()
st.subheader("🔥 Setting Hook / Teks")
hook_atas = st.text_input("Teks Atas (Hook)", "DIA MULAI BERUBAH")
hook_bawah = st.text_input("Teks Bawah", "TUNGGU SAMPE AKHIR!")
use_caption = st.checkbox("Aktifkan Auto Caption (Whisper)", value=True)
use_smart_cut = st.checkbox("Aktifkan Smart Cut - Cari Momen Paling Rame", value=True)

def run(cmd):
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except:
        return 0

def find_loud_moments(path, total, clip_dur, n_clips):
    scores = []
    step = 5
    for start in range(0, int(total - clip_dur), step):
        tmp = "temp_vol.wav"
        run(["ffmpeg", "-y", "-ss", str(start), "-t", str(clip_dur), "-i", path, "-vn", "-ac", "1", "-ar", "16000", tmp])
        if not os.path.exists(tmp):
            continue
        r = subprocess.run(["ffmpeg", "-i", tmp, "-af", "volumedetect", "-f", "null", "/dev/null"], capture_output=True, text=True, stderr=subprocess.STDOUT)
        m = re.search(r"mean_volume: (.*) dB", r.stdout + r.stderr)
        vol = float(m.group(1)) if m else -99
        scores.append((start, vol))
        if os.path.exists(tmp):
            os.remove(tmp)
    scores = sorted(scores, key=lambda x: x[1], reverse=True)
    picked = []
    for s, v in scores:
        if all(abs(s - p) > clip_dur for p in picked):
            picked.append(s)
        if len(picked) >= n_clips:
            break
    return sorted(picked) if picked else [0]

if st.button("👑 BUAT CLIP PRO", type="primary"):
    uid = str(uuid.uuid4())[:8]
    os.makedirs(f"output/{uid}", exist_ok=True)
    raw = f"output/{uid}/raw.mp4"

    # --- LOGIC DOWNLOAD / UPLOAD ---
    if mode == "📁 Upload Video dari HP":
        if not uploaded_file:
            st.warning("Upload dulu videonya King!")
            st.stop()
        with open(raw, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("Upload beres!")
    else:
        if not url:
            st.warning("Isi link dulu King!")
            st.stop()
        with st.spinner("1/4 Lagi download..."):
            # Versi bandel, anti-block
            run(["yt-dlp", "-f", "best[ext=mp4]/best", "--no-playlist", "--user-agent", "Mozilla/5.0", "--remux-video", "mp4", "-o", raw, url])
        if not os.path.exists(raw) or os.path.getsize(raw) < 1000:
            st.error("Gagal download. Link kena block YouTube.")
            st.info("Solusi: Ganti ke mode 📁 Upload Video dari HP di atas, download dulu videonya pake SnapTik.")
            st.stop()

    total = get_duration(raw)
    if total == 0:
        st.error("File video rusak / format gak kebaca.")
        st.stop()
    st.success(f"Video masuk! Durasi {int(total)} detik")
    with st.spinner("2/4 Lagi nyari momen paling rame..."):
        if use_smart_cut:
            starts = find_loud_moments(raw, total, clip_duration, max_clips)
        else:
            starts = [i * clip_duration for i in range(max_clips)]
    srt_path = None
    if use_caption:
        with st.spinner("3/4 Lagi bikin caption pake Whisper..."):
            try:
                from faster_whisper import WhisperModel
                model = WhisperModel("tiny", device="cpu", compute_type="int8")
                segments, _ = model.transcribe(raw, language="id")
                srt_path = f"output/{uid}/cap.srt"
                with open(srt_path, "w", encoding="utf-8") as f:
                    for i, seg in enumerate(segments):
                        f.write(f"{i+1}\n")
                        f.write(f"00:{int(seg.start//60):02d}:{int(seg.start%60):02d},000 --> 00:{int(seg.end//60):02d}:{int(seg.end%60):02d},000\n")
                        f.write(f"{seg.text.strip()}\n\n")
            except Exception as e:
                st.warning(f"Caption gagal, lanjut tanpa caption: {e}")
                srt_path = None
    st.subheader("Hasilnya King 👇")
    for idx, start in enumerate(starts):
        out = f"output/{uid}/final_{idx+1}.mp4"
        top = hook_atas.replace("'", "").replace(":", "\\:")
        bot = hook_bawah.replace("'", "").replace(":", "\\:")
        vf = "crop=ih*9/16:ih,scale=1080:1920,"
        vf += f"drawtext=text='{top}':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:fontsize=70:fontcolor=yellow:borderw=5:bordercolor=black:x=(w-text_w)/2:y=80,"
        vf += f"drawtext=text='{bot}':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:fontsize=60:fontcolor=white:borderw=5:bordercolor=black:x=(w-text_w)/2:y=h-220"
        if srt_path and os.path.exists(srt_path):
            vf_final = vf + f",subtitles='{srt_path}':force_style='Fontsize=28,PrimaryColour=&H00FFFF&,Bold=1,Outline=2'"
        else:
            vf_final = vf
        cmd = ["ffmpeg", "-y", "-ss", str(start), "-t", str(clip_duration), "-i", raw, "-vf", vf_final, "-c:a", "aac", out]
        with st.spinner(f"Render clip {idx+1} / mulai detik {start}..."):
            run(cmd)
        if os.path.exists(out):
            st.video(out)
            st.write(f"**Clip {idx+1}** - Mulai detik {start} (Momen Rame)")
            with open(out, "rb") as f:
                st.download_button(f"Download Clip {idx+1}", f, file_name=f"clip_{idx+1}.mp4", mime="video/mp4")
