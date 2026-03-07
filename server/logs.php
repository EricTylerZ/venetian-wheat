<?php
/**
 * Venetian Wheat — Access Log Reader
 * Returns recent access log entries (called by dashboard).
 *
 * Endpoint: GET /wheat-api/logs.php?limit=100&domain=&ip=&event=
 * Auth: X-Wheat-Key header
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-Wheat-Key');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

require_once __DIR__ . '/config.php';

$api_key = $_SERVER['HTTP_X_WHEAT_KEY'] ?? '';
if ($api_key !== WHEAT_API_KEY) {
    http_response_code(401);
    echo json_encode(['error' => 'unauthorized']);
    exit;
}

try {
    $pdo = new PDO(
        'mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=utf8mb4',
        DB_USER,
        DB_PASS,
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
    );

    $limit  = min((int)($_GET['limit']  ?? 100), 500);
    $domain = $_GET['domain'] ?? '';
    $ip     = $_GET['ip']     ?? '';
    $event  = $_GET['event']  ?? '';

    $where  = [];
    $params = [];

    if ($domain) { $where[] = 'domain = :domain'; $params[':domain'] = $domain; }
    if ($ip)     { $where[] = 'ip = :ip';         $params[':ip']     = $ip;     }
    if ($event)  { $where[] = 'event = :event';   $params[':event']  = $event;  }

    $sql = "SELECT id, ip, page, referrer, domain, event, user_hash, created_at
            FROM access_log"
         . ($where ? ' WHERE ' . implode(' AND ', $where) : '')
         . " ORDER BY created_at DESC LIMIT :limit";

    $stmt = $pdo->prepare($sql);
    foreach ($params as $k => $v) { $stmt->bindValue($k, $v); }
    $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
    $stmt->execute();

    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    // Summary counts
    $unique_ips = count(array_unique(array_column($rows, 'ip')));

    echo json_encode([
        'ok'         => true,
        'count'      => count($rows),
        'unique_ips' => $unique_ips,
        'logs'       => $rows,
    ]);

} catch (PDOException $e) {
    error_log('[wheat-logs] DB error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'db_error']);
}
