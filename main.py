from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from config import settings
import subprocess
import uuid
import json
import shutil
import threading
from datetime import datetime

BASE_DIR = Path("jobs")
BASE_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Auto Subtitle Service", version="1.0")

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# --------------------
# Models
# --------------------
class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int | None = None
    created_at: str

# --------------------
# Helpers
# --------------------
def job_path(job_id: str) -> Path:
    return BASE_DIR / job_id


def meta_path(job_id: str) -> Path:
    return job_path(job_id) / "meta.json"


def read_meta(job_id: str) -> dict:
    p = meta_path(job_id)
    if not p.exists():
        raise HTTPException(404, "Job not found")
    return json.loads(p.read_text())


def write_meta(job_id: str, data: dict):
    meta_path(job_id).write_text(json.dumps(data, indent=2))

# --------------------
# Worker
# --------------------
def process_job(job_id: str, language: str, burn_in: bool):
    meta = read_meta(job_id)
    try:
        jobdir = job_path(job_id)
        meta.update({"status": "processing", "progress": 5})
        write_meta(job_id, meta)

        video = jobdir / meta["filename"]
        audio = jobdir / "audio.wav"
        output_subtitle = jobdir / "subtitle"

        # Extract audio
        subprocess.run([
            "ffmpeg", "-y", "-i", str(video),
            "-vn", "-ac", "1", "-ar", "16000", str(audio)
        ], check=True)

        meta["progress"] = 30
        write_meta(job_id, meta)

        # Whisper.cpp
        whisper_cmd = [
            "whisper-cli",
            "-m", settings.model_path,
            "-f", str(audio),
            "--output-srt",
            "--output-txt",
            "--output-file", str(output_subtitle)
        ]

        if language != "auto":
            whisper_cmd += ["-l", language]

        subprocess.run(whisper_cmd, check=True)

        meta["progress"] = 70
        write_meta(job_id, meta)

        # Burn subtitles
        if burn_in:
            srt = jobdir / "subtitle.srt"
            out_video = jobdir / "output.mp4"
            subprocess.run([
                "ffmpeg", "-y", "-i", str(video),
                "-vf", f"subtitles={srt}",
                str(out_video)
            ], check=True)

        meta.update({"status": "completed", "progress": 100})
        write_meta(job_id, meta)

    except Exception as e:
        meta.update({"status": "failed", "error": str(e)})
        write_meta(job_id, meta)

# --------------------
# API Endpoints
# --------------------
@app.post("/api/v1/jobs")
async def create_job(
    file: UploadFile = File(...),
    language: str = Form('auto'),
    burn_in: bool = Form(True)
):
    job_id = str(uuid.uuid4())
    jobdir = job_path(job_id)
    jobdir.mkdir()
    filename = f"{job_id}.mp4"

    video_path = jobdir / filename
    with open(video_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    meta = {
        "job_id": job_id,
        "filename": filename,
        "status": "queued",
        "progress": 0,
        "created_at": datetime.utcnow().isoformat()
    }
    write_meta(job_id, meta)

    threading.Thread(
        target=process_job,
        args=(job_id, language, burn_in),
        daemon=True
    ).start()

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/v1/jobs/{job_id}", response_model=JobStatus)
def get_status(job_id: str):
    meta = read_meta(job_id)
    return meta


@app.get("/api/v1/jobs/{job_id}/subtitle")
def download_subtitle(job_id: str):
    jobdir = job_path(job_id)
    subtitle = jobdir / "subtitle.srt"
    if not subtitle.exists():
        raise HTTPException(404, "Subtitle not ready")
    return FileResponse(subtitle, filename=subtitle.name)


@app.get("/api/v1/jobs/{job_id}/video")
def download_video(job_id: str):
    video = job_path(job_id) / "output.mp4"
    if not video.exists():
        raise HTTPException(404, "Video not available")
    return FileResponse(video, filename="output.mp4")


@app.get("/api/v1/jobs/{job_id}/transcript")
def get_transcript(job_id: str):
    txt = job_path(job_id) / "subtitle.txt"
    if not txt.exists():
        raise HTTPException(404, "Transcript not ready")
    return {"text": txt.read_text()}


@app.delete("/api/v1/jobs/{job_id}")
def delete_job(job_id: str):
    jobdir = job_path(job_id)
    if not jobdir.exists():
        raise HTTPException(404, "Job not found")
    shutil.rmtree(jobdir)
    return {"deleted": True}
