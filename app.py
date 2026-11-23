import streamlit as st
import os, subprocess, uuid, json, random

st.set_page_config(page_title="AutoClip PRO", page_icon="👑")
st.title("👑 AutoClip PRO - YT / TikTok")
st.write("Paste link -> Auto cari momen rame -> Auto caption -> Auto hook. Tinggal upload.")

url = st.text_input("Paste Link YT / TikTok", placeholder="https://...")
clip_duration = st.slider("Durasi clip", 15, 60, 30)
max_clips = st.slider("Jumlah clip", 1, 5, 3)

# --- SETTING HOOK ---
st.divider()
st.subheader("🔥 Setting Hook / Teks")
hook_atas = st.text_input("Teks Atas (Hook)", "DIA MULAI BERUBAH")
hook_bawah = st.text_input("Teks Bawah", "TUNGGU SAMPE AKHIR!")
use_caption = st.checkbox("Aktifkan Auto Caption (Whisper)", value=True)
use_smart_cut = st.checkbox("Aktifkan Smart Cut - Cari Momen Paling Rame", value=True)

def run(cmd):
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_duration(path):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except: return 0

def find_loud_moments(path, total, clip_dur, n_clips):
    # Bagi video jadi potongan 5 detik, cek volume tiap potongan
    scores = []
    step = 5
    for start in range(0, int(total - clip_dur), step):
        tmp = f"temp_vol.wav"
        run(["ffmpeg","-y","-ss",str(start),"-t",str(clip_dur),"-i",path,"-vn","-ac","1","-ar","16000",tmp])
        if not os.path.exists(tmp): continue
        r = subprocess.run(["ffmpeg","-i",tmp,"-af","volumedetect","-f","null","/dev/null"],
            capture_output=True, text=True, stderr=subprocess.STDOUT)
        # ambil mean_volume
        import re
        m = re.search(r"mean_volume: (.*) dB", r.stdout + r.stderr)
        vol = float(m.group(1)) if m else -99
        scores.append((start, vol))
        if os.path.exists(tmp): os.remove(tmp)
    # Urutkan dari paling kenceng
    scores = sorted(scores, key=lambda x: x[1], reverse=True)
    # Biar gak numpuk di tempat yang sama, ambil yang jaraknya jauh
    picked = []
    for s, v in scores:
        if all(abs(s-p) > clip_dur for p in picked):
            picked.append(s)
        if len(picked) >= n_clips: break
    return sorted(picked) if picked else [0]

if st.button("👑 BUAT CLIP PRO", type="primary"):
    if not url:
        st.warning("Isi link dulu King!")
    else:
        uid = str(uuid.uuid4())[:8]
        os.makedirs(f"output/{uid}", exist_ok=True)
        raw = f"output/{uid}/raw.mp4"
        with st.spinner("1/4 Lagi download..."):
            run(["yt-dlp","-f","mp4","-o",raw, url])
        if not os.path.exists(raw):
            st.error("Gagal download. Link private / kena block.")
            st.stop()

        total = get_duration(raw)
        st.success(f"Download beres! Durasi {int(total)} detik")

        # 2. Smart Cut
        with st.spinner("2/4 Lagi nyari momen paling rame..."):
            if use_smart_cut:
                starts = find_loud_moments(raw, total, clip_duration, max_clips)
            else:
                starts = [i*clip_duration for i in range(max_clips)]

        # 3. Whisper Caption
        srt_path = None
        if use_caption:
            with st.spinner("3/4 Lagi bikin caption pake Whisper... (agak lama)"):
                try:
                    from faster_whisper import WhisperModel
                    model = WhisperModel("small", device="cpu", compute_type="int8")
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

        # 4. Render Final
        st.subheader("Hasilnya King 👇")
        for idx, start in enumerate(starts):
            out = f"output/{uid}/final_{idx+1}.mp4"
            # Filter: crop 9:16 + teks atas bawah + subtitle
            # Escape teks buat ffmpeg
            top = hook_atas.replace("'","").replace(":","\\:")
            bot = hook_bawah.replace("'","").replace(":","\\:")
            
            vf = f"crop=ih*9/16:ih,scale=1080:1920,"
vf += f"drawtext=text='{top}':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:fontsize=70:fontcolor=yellow:borderw=5:bordercolor=black:x=(w-text_w)/2:y=80,"
vf += f"drawtext=text='{bot}':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:fontsize=60:fontcolor=white:borderw=5:bordercolor=black:x=(w-text_w)/2:y=h-220"
            
            cmd = ["ffmpeg","-y","-ss",str(start),"-t",str(clip_duration),"-i",raw,
                   "-vf", vf, "-c:a","aac", out]
            
            # Kalau ada caption, tambahin subtitle burn-in
            if srt_path and os.path.exists(srt_path):
                # Bikin versi subtitle style TikTok
                vf_sub = vf + f",subtitles='{srt_path}':force_style='Fontsize=28,PrimaryColour=&H00FFFF&,Bold=1,Outline=2'"
                cmd = ["ffmpeg","-y","-ss",str(start),"-t",str(clip_duration),"-i",raw,
                       "-vf", vf_sub, "-c:a","aac", out]

            with st.spinner(f"Render clip {idx+1} / mulai detik {start}..."):
                run(cmd)
            
            if os.path.exists(out):
                st.video(out)
                st.write(f"**Clip {idx+1}** - Mulai detik {start} (Momen Rame)")
                with open(out,"rb") as f:
                    st.download_button(f"⬇️ Download Clip {idx+1}", f, file_name=f"clip_{idx+1}.mp4", mime="video/mp4")
