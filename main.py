import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.tasks import process_video_task
from app.job_store import job_store

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "storage" / "uploads"
RESULT_DIR = BASE_DIR / "storage" / "results"
FRONTEND_DIR = BASE_DIR.parent / "frontend"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

MAX_BYTES = 500 * 1024 * 1024  # 500MB
ALLOWED_CONTENT_TYPES = {"video/mp4", "video/quicktime", "video/webm", "video/x-matroska"}

app = FastAPI(title="Clearcut API")

# Loosen this in production — restrict to your actual frontend origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    job_id = str(uuid.uuid4())
    suffix = Path(file.filename).suffix or ".mp4"
    input_path = UPLOAD_DIR / f"{job_id}{suffix}"

    size = 0
    with open(input_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_BYTES:
                out.close()
                input_path.unlink(missing_ok=True)
                raise HTTPException(400, "File exceeds 500MB limit")
            out.write(chunk)

    job_store.create(job_id)

    # Hand off to the Celery worker — this returns immediately.
    process_video_task.delay(job_id, str(input_path))

    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job id")
    return job


@app.get("/api/results/{job_id}.mp4")
async def get_result(job_id: str):
    result_path = RESULT_DIR / f"{job_id}.mp4"
    if not result_path.exists():
        raise HTTPException(404, "Result not ready")
    return FileResponse(result_path, media_type="video/mp4")


# Serve the plain HTML/CSS/JS frontend as static files.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
