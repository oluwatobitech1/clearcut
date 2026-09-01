import os
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "clearcut",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Video jobs are long-running and CPU/GPU heavy — one at a time per worker
    # process avoids fighting over the same GPU. Scale by running more worker
    # processes/machines, not more concurrency per process.
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
