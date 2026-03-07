<?php
/**
 * Venetian Wheat — Access Logger
 * Logs visitor IP, page, user-agent to MySQL for security monitoring.
 * Called by Vercel dashboard OR directly by Apache via auto-include.
 *
 * Endpoint: POST /wheat-api/log.php
 * Auth: X-Wheat-Key header must match WHEAT_API_KEY in config.php
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-Wheat-Key');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

require_once __DIR__ . '/config.php';

// --- Auth check ---
$api_key = $_SERVER['HTTP_X_WHEAT_KEY'] ?? '';
if ($api_key !== WHEAT_API_KEY) {
    http_response_code(401);
    echo json_encode(['error' => 'unauthorized']);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'method not allowed']);
    exit;
}

$body = json_decode(file_get_contents('php://input'), true);

// --- Collect data ---
$ip        = $_SERVER['HTTP_CF_CONNECTING_IP']     // Cloudflare real IP
          ?? $_SERVER['HTTP_X_FORWARDED_FOR']       // proxy
          ?? $_SERVER['REMOTE_ADDR']                // direct
          ?? 'unknown';
$ip        = strtok($ip, ',');  // X-Forwarded-For can be comma-list; take first

$page      = substr($body['page']       ?? '', 0, 500);
$referrer  = substr($body['referrer']   ?? '', 0, 500);
$ua        = substr($_SERVER['HTTP_USER_AGENT'] ?? $body['user_agent'] ?? '', 0, 500);
$domain    = substr($body['domain']     ?? '', 0, 100);
$event     = substr($body['event']      ?? 'pageview', 0, 50);
$user_hash = substr($body['user_hash']  ?? '', 0, 64);  // hashed session id, not raw

// --- Write to MySQL ---
try {
    $pdo = new PDO(
        'mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=utf8mb4',
        DB_USER,
        DB_PASS,
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
    );

    $stmt = $pdo->prepare("
        INSERT INTO access_log (ip, page, referrer, user_agent, domain, event, user_hash, created_at)
        VALUES (:ip, :page, :referrer, :ua, :domain, :event, :user_hash, NOW())
    ");
    $stmt->execute([
        ':ip'        => $ip,
        ':page'      => $page,
        ':referrer'  => $referrer,
        ':ua'        => $ua,
        ':domain'    => $domain,
        ':event'     => $event,
        ':user_hash' => $user_hash,
    ]);

    echo json_encode(['ok' => true, 'id' => $pdo->lastInsertId()]);

} catch (PDOException $e) {
    error_log('[wheat-log] DB error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'db_error']);
}
