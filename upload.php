<?php
/**
 * POST /api/upload
 *
 * Accepts a multipart video upload, validates it, saves it to disk, creates
 * a job record, and pushes it onto the Redis queue for the Python worker
 * to pick up. Returns { job_id } immediately — processing happens async.
 */

require_once __DIR__ . '/config.php';
require_once __DIR__ . '/ApiResponse.php';
require_once __DIR__ . '/RedisJobStore.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    ApiResponse::error('Method not allowed', 405);
}

if (!isset($_FILES['file']) || $_FILES['file']['error'] !== UPLOAD_ERR_OK) {
    $uploadError = $_FILES['file']['error'] ?? UPLOAD_ERR_NO_FILE;
    if ($uploadError === UPLOAD_ERR_INI_SIZE || $uploadError === UPLOAD_ERR_FORM_SIZE) {
        ApiResponse::error('File exceeds server upload limit', 400);
    }
    ApiResponse::error('No video file was received', 400);
}

$file = $_FILES['file'];

if ($file['size'] > MAX_UPLOAD_BYTES) {
    ApiResponse::error('File exceeds 500MB limit', 400);
}

// Validate actual file content, not just the client-supplied header.
$detectedType = mime_content_type($file['tmp_name']);
if (!in_array($detectedType, ALLOWED_VIDEO_TYPES, true)) {
    ApiResponse::error("Unsupported file type: {$detectedType}", 400);
}

$jobId = bin2hex(random_bytes(16));
$extension = pathinfo($file['name'], PATHINFO_EXTENSION) ?: 'mp4';
$destination = UPLOAD_DIR . "/{$jobId}.{$extension}";

if (!move_uploaded_file($file['tmp_name'], $destination)) {
    ApiResponse::error('Failed to save uploaded file', 500);
}

try {
    $jobStore = new RedisJobStore();
    $jobStore->create($jobId);
    $jobStore->enqueue($jobId, $destination);
} catch (RuntimeException $e) {
    unlink($destination);
    ApiResponse::error('Could not queue job: ' . $e->getMessage(), 500);
}

ApiResponse::success(['job_id' => $jobId], 'Upload received', 200);
