<?php
/**
 * Venetian Wheat — cPanel API Bridge
 * Exposes safe read-only cPanel UAPI calls to the dashboard.
 * Runs ON Namecheap so credentials never leave the server.
 *
 * Endpoint: GET /wheat-api/cpanel.php?action=<action>
 * Auth: X-Wheat-Key header
 *
 * Supported actions:
 *   domains       — list addon/sub domains
 *   dbs           — list MySQL databases
 *   emails        — list email accounts
 *   disk          — disk usage summary
 *   ssl           — SSL certificate status per domain
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

$action = $_GET['action'] ?? '';

// cPanel UAPI — available locally on shared hosting
// No external HTTP needed; cPanel exposes it via local socket or loopback
function cpanel_uapi(string $module, string $function, array $params = []): array {
    // cPanel sets $CPANEL_PHPLIB_DIR or we can use the CLI tool
    // On Namecheap shared hosting, use the cpanel CLI
    $query = http_build_query($params);
    $cmd   = 'uapi --output=json ' . escapeshellarg($module) . ' ' . escapeshellarg($function);
    if ($query) { $cmd .= ' ' . $query; }

    $output = shell_exec($cmd . ' 2>&1');
    if ($output === null) {
        return ['error' => 'uapi_unavailable'];
    }

    $decoded = json_decode($output, true);
    if (json_last_error() !== JSON_ERROR_NONE) {
        return ['error' => 'json_parse_error', 'raw' => substr($output, 0, 500)];
    }
    return $decoded['result'] ?? $decoded;
}

switch ($action) {
    case 'domains':
        $main   = cpanel_uapi('DomainInfo', 'main_domain');
        $addons = cpanel_uapi('AddonDomain', 'list_addon_domains');
        $subs   = cpanel_uapi('SubDomain', 'listsubdomains');
        echo json_encode([
            'ok'     => true,
            'main'   => $main['data'] ?? null,
            'addons' => $addons['data'] ?? [],
            'subs'   => $subs['data']  ?? [],
        ]);
        break;

    case 'dbs':
        $result = cpanel_uapi('Mysql', 'list_databases');
        echo json_encode([
            'ok'  => true,
            'dbs' => $result['data'] ?? [],
        ]);
        break;

    case 'emails':
        $result = cpanel_uapi('Email', 'list_pops');
        echo json_encode([
            'ok'     => true,
            'emails' => $result['data'] ?? [],
        ]);
        break;

    case 'disk':
        $result = cpanel_uapi('Quota', 'get_quota_info');
        echo json_encode([
            'ok'   => true,
            'disk' => $result['data'] ?? null,
        ]);
        break;

    case 'ssl':
        $result = cpanel_uapi('SSL', 'list_certs');
        echo json_encode([
            'ok'   => true,
            'certs'=> $result['data'] ?? [],
        ]);
        break;

    default:
        http_response_code(400);
        echo json_encode([
            'error'   => 'unknown_action',
            'actions' => ['domains', 'dbs', 'emails', 'disk', 'ssl'],
        ]);
}
