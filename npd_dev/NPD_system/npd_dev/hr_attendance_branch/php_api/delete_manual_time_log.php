<?php
// ลบเรคคอร์ดในตาราง manual_time_logs (เรียกจาก Odoo ตอนกดลบ)
// รับ JSON body: { "id": <int> }

$db_host = 'localhost';
$db_name = 'npdhr_dbbase_npd';
$db_user = 'npdhr_dbbase_npd';
$db_pass = '@Npd78901234';

$correct_username = 'Npd_admin';
$correct_password = '78901234';

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

    $pdo = new PDO("mysql:host=$db_host;dbname=$db_name;charset=utf8", $db_user, $db_pass);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    $stmt = $pdo->prepare("DELETE FROM manual_time_logs WHERE id = ?");
    $stmt->execute([$id]);

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
