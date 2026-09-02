"""
Clearcut worker.

Run this as a long-lived process (systemd service, supervisor, tmux — same
idea as a Celery worker, just without Celery). It blocks on the Redis list
that api/upload.php pushes to, and writes status updates to the same
job:{id} Redis keys that api/jobs.php reads from. No message broker
protocol involved — just a plain Redis list and JSON blobs, so both the
PHP and Python sides can talk to it without either depending on the other's
framework.

Run:
    python worker.py
"""

import json
import os
import time
from pathlib import Path

import redis

from app.job_store import job_store
from app import pipeline

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
QUEUE_KEY = "clearcut:queue"

# Shared storage lives at the project root (../storage relative to backend/)
# so both this worker and the PHP API (api/config.php) point at the same
# directory on disk.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULT_DIR = PROJECT_ROOT / "storage" / "results"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

# socket_timeout must exceed BLPOP's own timeout below, or the client-side
# socket read times out first and raises before Redis's own timeout fires.
_r = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=10)


def process_job(job_id: str, input_path: str) -> None:
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
        Path(input_path).unlink(missing_ok=True)


def main() -> None:
    print(f"Clearcut worker started, watching '{QUEUE_KEY}' on {REDIS_URL}")
    while True:
        # Blocks until a job appears; timeout=5 just lets the loop wake up
        # periodically rather than blocking forever on a dead connection.
        try:
            item = _r.blpop(QUEUE_KEY, timeout=5)
        except redis.exceptions.TimeoutError:
            continue
        if item is None:
            continue

        _, raw = item
        try:
            payload = json.loads(raw)
            job_id = payload["job_id"]
            input_path = payload["input_path"]
        except (json.JSONDecodeError, KeyError) as exc:
            print(f"Skipping malformed queue item: {exc}")
            continue

        print(f"Processing job {job_id}")
        try:
            process_job(job_id, input_path)
            print(f"Job {job_id} done")
        except Exception as exc:  # noqa: BLE001
            print(f"Job {job_id} failed: {exc}")


if __name__ == "__main__":
    main()
