<?php
/**
 * GET /api/jobs/{id}  ->  rewritten to jobs.php?id={id}
 *
 * Returns the current status of a job. This is read-only from PHP's side —
 * the Python worker is what actually updates progress/status in Redis as
 * it works through detection -> inpainting -> encoding.
 */

require_once __DIR__ . '/config.php';
require_once __DIR__ . '/ApiResponse.php';
require_once __DIR__ . '/RedisJobStore.php';

if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    ApiResponse::error('Method not allowed', 405);
}

$jobId = $_GET['id'] ?? '';
if ($jobId === '' || !preg_match('/^[a-f0-9]{32}$/', $jobId)) {
    ApiResponse::error('Invalid job id', 400);
}

try {
    $jobStore = new RedisJobStore();
    $job = $jobStore->get($jobId);
} catch (RuntimeException $e) {
    ApiResponse::error('Could not reach job store: ' . $e->getMessage(), 500);
}

if ($job === null) {
    ApiResponse::notFound('Unknown job id');
}

ApiResponse::success($job, 'OK', 200);
