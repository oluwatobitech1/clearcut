<?php
// Router for PHP's built-in dev server: mimics .htaccess rewrite rules
// so /api/upload, /api/jobs/{id}, /api/results/{id}.mp4 resolve correctly
// without needing Apache. Not used in production (real Apache reads
// .htaccess directly) — this file is local-testing only.

$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);

if (preg_match('#^/api/upload/?$#', $uri)) {
    require __DIR__ . '/api/upload.php';
    return true;
}
if (preg_match('#^/api/jobs/([a-f0-9]+)/?$#', $uri, $m)) {
    $_GET['id'] = $m[1];
    require __DIR__ . '/api/jobs.php';
    return true;
}
if (preg_match('#^/api/results/([a-f0-9]+)\.mp4$#', $uri, $m)) {
    $_GET['id'] = $m[1];
    require __DIR__ . '/api/results.php';
    return true;
}

// Static files (frontend)
$path = __DIR__ . '/frontend' . $uri;
if ($uri !== '/' && file_exists($path) && !is_dir($path)) {
    return false; // let built-in server handle it directly
}
require __DIR__ . '/frontend/index.html';
