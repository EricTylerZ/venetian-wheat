<?php
/**
 * Venetian Wheat — Shared Data API
 * Key/value store shared across all your domains and subdomains.
 * One MySQL table, accessible from any domain via this endpoint.
 *
 * GET  /wheat-api/shared.php?key=myKey&domain=ericzosso.com
 * POST /wheat-api/shared.php  body: {"key":"myKey","value":"...","domain":""}
 * DELETE /wheat-api/shared.php?key=myKey&domain=ericzosso.com
 *
 * domain="" means global (shared across ALL domains)
 * domain="ericzosso.com" means scoped to that domain only
 *
 * Auth: X-Wheat-Key header
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, DELETE, OPTIONS');
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

    $method = $_SERVER['REQUEST_METHOD'];
    $key    = $_GET['key']    ?? '';
    $domain = $_GET['domain'] ?? '';

    if ($method === 'GET') {
        if (!$key) {
            // List all keys for a domain
            $stmt = $pdo->prepare("SELECT `key`, `value`, domain, updated_at FROM shared_data WHERE domain = :domain ORDER BY `key`");
            $stmt->execute([':domain' => $domain]);
            echo json_encode(['ok' => true, 'data' => $stmt->fetchAll(PDO::FETCH_ASSOC)]);
            exit;
        }
        $stmt = $pdo->prepare("SELECT `value`, updated_at FROM shared_data WHERE `key` = :key AND domain = :domain");
        $stmt->execute([':key' => $key, ':domain' => $domain]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);
        if (!$row) {
            http_response_code(404);
            echo json_encode(['error' => 'not_found']);
            exit;
        }
        echo json_encode(['ok' => true, 'key' => $key, 'value' => $row['value'], 'updated_at' => $row['updated_at']]);

    } elseif ($method === 'POST') {
        $body   = json_decode(file_get_contents('php://input'), true) ?? [];
        $key    = substr($body['key']    ?? '', 0, 255);
        $value  = $body['value']  ?? '';
        $domain = substr($body['domain'] ?? '', 0, 100);

        if (!$key) {
            http_response_code(400);
            echo json_encode(['error' => 'key_required']);
            exit;
        }
        $stmt = $pdo->prepare("
            INSERT INTO shared_data (`key`, `value`, domain)
            VALUES (:key, :value, :domain)
            ON DUPLICATE KEY UPDATE `value` = VALUES(`value`), updated_at = NOW()
        ");
        $stmt->execute([':key' => $key, ':value' => $value, ':domain' => $domain]);
        echo json_encode(['ok' => true, 'key' => $key]);

    } elseif ($method === 'DELETE') {
        if (!$key) {
            http_response_code(400);
            echo json_encode(['error' => 'key_required']);
            exit;
        }
        $stmt = $pdo->prepare("DELETE FROM shared_data WHERE `key` = :key AND domain = :domain");
        $stmt->execute([':key' => $key, ':domain' => $domain]);
        echo json_encode(['ok' => true, 'deleted' => $stmt->rowCount()]);

    } else {
        http_response_code(405);
        echo json_encode(['error' => 'method_not_allowed']);
    }

} catch (PDOException $e) {
    error_log('[wheat-shared] DB error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'db_error']);
}
