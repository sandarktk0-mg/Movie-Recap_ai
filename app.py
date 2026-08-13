import os, uuid, json, math, re, subprocess
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE = Path(__file__).parent
UPLOADS = BASE / "uploads"
OUTPUTS = BASE / "outputs"
UPLOADS.mkdir(exist_ok=True)
OUTPUTS.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2GB

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None
TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-5.6-mini")
TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "coral")

JOBS = {}

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-2000:] or "FFmpeg error")
    return p

def probe_duration(path):
    p = run(["ffprobe","-v","error","-show_entries","format=duration",
             "-of","default=noprint_wrappers=1:nokey=1",str(path)])
    return float(p.stdout.strip())

def make_srt(text, duration, out):
    # Simple readable subtitle timing for the generated narration.
    chunks = [x.strip() for x in re.split(r"(?<=[။!?])\s+|\n+", text) if x.strip()]
    if not chunks:
        chunks = [text.strip()]
    weights = [max(1, len(c)) for c in chunks]
    total = sum(weights)
    t = 0.0
    lines = []
    for i, chunk in enumerate(chunks, 1):
        d = duration * weights[i-1] / total
        start, end = t, min(duration, t+d)
        def ts(x):
            ms = int(round((x-int(x))*1000))
            sec = int(x)
            h, sec = divmod(sec, 3600)
            m, sec = divmod(sec, 60)
            return f"{h:02}:{m:02}:{sec:02},{ms:03}"
        lines.append(f"{i}\n{ts(start)} --> {ts(end)}\n{chunk}\n")
        t = end
    out.write_text("\n".join(lines), encoding="utf-8")

def process_job(job_id, video_path, style):
    try:
        JOBS[job_id] = {"status":"processing","progress":8,"message":"Audio ထုတ်နေပါတယ်…"}
        wav = OUTPUTS / f"{job_id}.wav"
        run(["ffmpeg","-y","-i",str(video_path),"-vn","-ac","1","-ar","16000",str(wav)])

        JOBS[job_id] = {"status":"processing","progress":20,"message":"Movie dialogue ကို စာသားပြောင်းနေပါတယ်…"}
        if not client:
            raise RuntimeError("OPENAI_API_KEY မထည့်ရသေးပါ။ .env ဖိုင်ထဲထည့်ပါ။")

        with wav.open("rb") as f:
            tr = client.audio.transcriptions.create(
                model=TRANSCRIBE_MODEL,
                file=f,
                response_format="text"
            )
        transcript = getattr(tr, "text", None) or str(tr)

        JOBS[job_id] = {"status":"processing","progress":42,"message":"မြန်မာ Movie Recap Script ရေးနေပါတယ်…"}
        prompt = f"""
You are a professional Burmese movie-recap narrator.
Turn the following movie transcript into an engaging Burmese recap narration.
Style: {style}.
Rules:
- Write natural spoken Myanmar Burmese, not formal essay prose.
- Explain the story clearly in chronological order.
- Keep names and important plot points.
- Do not invent events that are not supported by the transcript.
- Avoid dialogue quotation unless essential.
- Make it sound good for a YouTube/TikTok voice-over.
- Return ONLY the narration script in Burmese.
Transcript:
{transcript[:120000]}
"""
        resp = client.responses.create(model=TEXT_MODEL, input=prompt)
        script = resp.output_text.strip()

        JOBS[job_id] = {"status":"processing","progress":62,"message":"မြန်မာ AI Voice ထုတ်နေပါတယ်…"}
        speech = OUTPUTS / f"{job_id}_voice.mp3"
        with speech.open("wb") as f:
            audio = client.audio.speech.create(
                model=TTS_MODEL,
                voice=TTS_VOICE,
                input=script,
                instructions="Speak naturally in Burmese/Myanmar language, with clear narration and moderate cinematic emotion."
            )
            f.write(audio.read())

        JOBS[job_id] = {"status":"processing","progress":76,"message":"Subtitle ပြင်ဆင်နေပါတယ်…"}
        voice_duration = probe_duration(speech)
        srt = OUTPUTS / f"{job_id}.srt"
        make_srt(script, voice_duration, srt)

        JOBS[job_id] = {"status":"processing","progress":88,"message":"Final MP4 render လုပ်နေပါတယ်…"}
        final = OUTPUTS / f"{job_id}_recap.mp4"

        # Original video is muted and used as visual background; AI narration is the audio.
        # This keeps the generated voice synchronized with the final file.
        run([
            "ffmpeg","-y","-i",str(video_path),"-i",str(speech),
            "-map","0:v:0","-map","1:a:0",
            "-c:v","libx264","-preset","veryfast","-crf","28",
            "-c:a","aac","-b:a","128k","-shortest",
            "-vf",f"subtitles={str(srt).replace(chr(92),'/')}",
            str(final)
        ])

        JOBS[job_id] = {
            "status":"done","progress":100,"message":"ပြီးပါပြီ 🎉",
            "video":f"/download/{job_id}_recap.mp4",
            "script":script
        }
    except Exception as e:
        JOBS[job_id] = {"status":"error","progress":0,"message":str(e)}

@app.route("/")
def index():
    return render_template("index.html")

@app.post("/api/upload")
def upload():
    f = request.files.get("video")
    if not f or not f.filename:
        return jsonify(error="Video file ရွေးပါ"), 400
    job_id = uuid.uuid4().hex
    ext = Path(f.filename).suffix.lower()
    if ext not in {".mp4",".mov",".mkv",".webm",".avi"}:
        return jsonify(error="MP4/MOV/MKV/WEBM/AVI သာ အသုံးပြုပါ"), 400
    path = UPLOADS / f"{job_id}{ext}"
    f.save(path)
    JOBS[job_id] = {"status":"uploaded","progress":2,"message":"Upload ပြီးပါပြီ"}
    return jsonify(job_id=job_id)

@app.post("/api/generate")
def generate():
    data = request.get_json(force=True)
    job_id = data.get("job_id")
    style = data.get("style","cinematic")
    if job_id not in JOBS:
        return jsonify(error="Job မတွေ့ပါ"), 404
    matches = list(UPLOADS.glob(job_id + ".*"))
    if not matches:
        return jsonify(error="Uploaded video မတွေ့ပါ"), 404
    import threading
    threading.Thread(target=process_job, args=(job_id,matches[0],style), daemon=True).start()
    return jsonify(ok=True)

@app.get("/api/status/<job_id>")
def status(job_id):
    return jsonify(JOBS.get(job_id, {"status":"missing","message":"Job မတွေ့ပါ"}))

@app.get("/download/<name>")
def download(name):
    return send_from_directory(OUTPUTS, name, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","5000")))
