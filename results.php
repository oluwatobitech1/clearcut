<?php
/**
 * GET /api/results/{id}.mp4  ->  rewritten to results.php?id={id}
 *
 * Streams the processed video back once the job is done. Kept separate
 * from jobs.php (JSON) since this returns a binary video stream instead.
 */

require_once __DIR__ . '/config.php';
require_once __DIR__ . '/ApiResponse.php';

$jobId = $_GET['id'] ?? '';
if ($jobId === '' || !preg_match('/^[a-f0-9]{32}$/', $jobId)) {
    ApiResponse::error('Invalid job id', 400);
}

$resultPath = RESULT_DIR . "/{$jobId}.mp4";
if (!is_file($resultPath)) {
    ApiResponse::notFound('Result not ready');
}

header('Content-Type: video/mp4');
header('Content-Length: ' . filesize($resultPath));
header('Content-Disposition: inline; filename="' . $jobId . '.mp4"');
header('Accept-Ranges: bytes');
readfile($resultPath);
exit;
