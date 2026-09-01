import json
import os
import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
JOB_TTL_SECONDS = 24 * 60 * 60  # matches the "deleted after 24h" note in the UI

_r = redis.from_url(REDIS_URL, decode_responses=True)


def _key(job_id: str) -> str:
    return f"job:{job_id}"


class JobStore:
    def create(self, job_id: str):
        job = {"job_id": job_id, "status": "queued", "progress": 0}
        _r.set(_key(job_id), json.dumps(job), ex=JOB_TTL_SECONDS)
        return job

    def get(self, job_id: str):
        raw = _r.get(_key(job_id))
        return json.loads(raw) if raw else None

    def update(self, job_id: str, **fields):
        job = self.get(job_id)
        if job is None:
            return None
        job.update(fields)
        _r.set(_key(job_id), json.dumps(job), ex=JOB_TTL_SECONDS)
        return job


job_store = JobStore()
