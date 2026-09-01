from pathlib import Path

from app.celery_app import celery_app
from app.job_store import job_store
from app import pipeline

BASE_DIR = Path(__file__).resolve().parent.parent
RESULT_DIR = BASE_DIR / "storage" / "results"
RESULT_DIR.mkdir(parents=True, exist_ok=True)


@celery_app.task(name="process_video")
def process_video_task(job_id: str, input_path: str):
    try:
        job_store.update(job_id, status="detecting", progress=10)
        frames, fps = pipeline.extract_frames(input_path)

        masks = pipeline.detect_text_masks(
            frames,
            on_progress=lambda pct: job_store.update(
                job_id, status="detecting", progress=10 + int(pct * 0.3)
            ),
        )

        job_store.update(job_id, status="inpainting", progress=40)
        inpainted_frames = pipeline.inpaint_frames(
            frames,
            masks,
            on_progress=lambda pct: job_store.update(
                job_id, status="inpainting", progress=40 + int(pct * 0.45)
            ),
        )

        job_store.update(job_id, status="encoding", progress=90)
        output_path = RESULT_DIR / f"{job_id}.mp4"
        pipeline.encode_video(inpainted_frames, fps, input_path, output_path)

        job_store.update(
            job_id,
            status="done",
            progress=100,
            result_url=f"/api/results/{job_id}.mp4",
        )

    except Exception as exc:  # noqa: BLE001 — surface any failure to the client
        job_store.update(job_id, status="failed", error=str(exc))
        raise

    finally:
        # Clean up the raw upload once we're done with it either way.
        Path(input_path).unlink(missing_ok=True)
