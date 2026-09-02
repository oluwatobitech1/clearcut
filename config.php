<?php
/**
 * Clearcut API config.
 * Same defined()-guard pattern as the site's existing config.php, so this
 * can be safely included alongside it without constant collisions.
 */

// Where uploaded videos and processed results are stored on disk.
if (!defined('UPLOAD_DIR')) {
    define('UPLOAD_DIR', __DIR__ . '/../storage/uploads');
}
if (!defined('RESULT_DIR')) {
    define('RESULT_DIR', __DIR__ . '/../storage/results');
}

// Upload limits.
if (!defined('MAX_UPLOAD_BYTES')) {
    define('MAX_UPLOAD_BYTES', 500 * 1024 * 1024); // 500MB
}
if (!defined('ALLOWED_VIDEO_TYPES')) {
    define('ALLOWED_VIDEO_TYPES', ['video/mp4', 'video/quicktime', 'video/webm', 'video/x-matroska']);
}

// Redis connection — shared job queue + job status store between this PHP
// API and the Python worker (see backend/worker.py).
if (!defined('REDIS_HOST')) {
    define('REDIS_HOST', getenv('REDIS_HOST') ?: '127.0.0.1');
}
if (!defined('REDIS_PORT')) {
    define('REDIS_PORT', getenv('REDIS_PORT') ?: 6379);
}
if (!defined('REDIS_QUEUE_KEY')) {
    define('REDIS_QUEUE_KEY', 'clearcut:queue');
}
if (!defined('JOB_TTL_SECONDS')) {
    define('JOB_TTL_SECONDS', 24 * 60 * 60); // matches "deleted after 24h" in the UI
}

foreach ([UPLOAD_DIR, RESULT_DIR] as $dir) {
    if (!is_dir($dir)) {
        mkdir($dir, 0775, true);
    }
}
