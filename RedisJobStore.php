<?php
/**
 * Shared job status store, backed by Redis.
 *
 * Mirrors backend/app/job_store.py exactly: same key format (job:{id}),
 * same JSON shape, same TTL. PHP writes the initial "queued" job and reads
 * status for polling; the Python worker (backend/worker.py) is the only
 * thing that transitions status beyond that.
 */

class RedisJobStore {

    private Redis $redis;

    public function __construct() {
        $this->redis = new Redis();
        $connected = $this->redis->connect(REDIS_HOST, (int) REDIS_PORT, 2.0);
        if (!$connected) {
            throw new RuntimeException('Could not connect to Redis at ' . REDIS_HOST . ':' . REDIS_PORT);
        }
    }

    private function key(string $jobId): string {
        return "job:{$jobId}";
    }

    public function create(string $jobId): array {
        $job = ['job_id' => $jobId, 'status' => 'queued', 'progress' => 0];
        $this->redis->set($this->key($jobId), json_encode($job), JOB_TTL_SECONDS);
        return $job;
    }

    public function get(string $jobId): ?array {
        $raw = $this->redis->get($this->key($jobId));
        if ($raw === false) {
            return null;
        }
        return json_decode($raw, true);
    }

    /** Push a job onto the queue the Python worker is BLPOP-ing from. */
    public function enqueue(string $jobId, string $inputPath): void {
        $payload = json_encode(['job_id' => $jobId, 'input_path' => $inputPath]);
        $this->redis->lPush(REDIS_QUEUE_KEY, $payload);
    }
}
