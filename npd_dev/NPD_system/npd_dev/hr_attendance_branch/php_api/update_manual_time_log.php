<?php
// อัพเดทเรคคอร์ดในตาราง manual_time_logs (เรียกจาก Odoo ตอนกดแก้ไข)
// รับ JSON body: { "id": <int>, "<column>": <value>, ... }

$db_host = 'localhost';
$db_name = 'npdhr_dbbase_npd';
$db_user = 'npdhr_dbbase_npd';
$db_pass = '@Npd78901234';

$correct_username = 'Npd_admin';
$correct_password = '78901234';

// คอลัมน์ที่อนุญาตให้แก้ไขได้ (whitelist กัน SQL injection / คอลัมน์ผิด)
$allowed_columns = [
    'user_id',
    'username',
    'work_date',
    'checkin_time',
    'checkout_time',
    'state',
    'user_note',
    'reason',
    'department',
    'position',
    'company',
    'reason_type',
    'allowance_type',
    'amount',
];

header('Content-Type: application/json');

try {
    $username = $_SERVER['PHP_AUTH_USER'] ?? '';
    $password = $_SERVER['PHP_AUTH_PW'] ?? '';

    if ($username !== $correct_username || $password !== $correct_password) {
        http_response_code(401);
        header('WWW-Authenticate: Basic realm="My API"');
        echo json_encode(['success' => false, 'error' => 'Unauthorized access. Invalid credentials.']);
        exit;
    }

    $input = json_decode(file_get_contents('php://input'), true);
    if (!is_array($input) || empty($input['id'])) {
        http_response_code(400);
        echo json_encode(['success' => false, 'error' => 'ต้องระบุ id']);
        exit;
    }

    $id = (int)$input['id'];

    $set_parts = [];
    $params = [];
    foreach ($input as $key => $value) {
        if ($key === 'id') {
            continue;
        }
        if (in_array($key, $allowed_columns, true)) {
            $set_parts[] = "`$key` = ?";
            $params[] = ($value === '' ? null : $value);
        }
    }

    if (empty($set_parts)) {
        echo json_encode(['success' => false, 'error' => 'ไม่มีคอลัมน์ที่อนุญาตให้แก้ไข']);
        exit;
    }

    $params[] = $id;

    $pdo = new PDO("mysql:host=$db_host;dbname=$db_name;charset=utf8", $db_user, $db_pass);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    $sql = "UPDATE manual_time_logs SET " . implode(', ', $set_parts) . " WHERE id = ?";
    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);

    echo json_encode([
        'success' => true,
        'id' => $id,
        'rows_affected' => $stmt->rowCount(),
    ]);

} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'MySQL: ' . $e->getMessage()]);
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => $e->getMessage()]);
}
?>
