<?php
// ข้อมูลการเชื่อมต่อฐานข้อมูล MySQL
$db_host = 'localhost';
$db_name = 'npdhr_dbbase_npd';
$db_user = 'npdhr_dbbase_npd';
$db_pass = '@Npd78901234';

// ข้อมูลการเข้าสู่ระบบที่ถูกต้อง
$correct_username = 'Npd_admin';
$correct_password = '78901234';

// ตั้งค่า Header ให้เป็น JSON
header('Content-Type: application/json');

try {
    // อ่านข้อมูลการเข้าสู่ระบบจาก HTTP Basic Authentication
    $username = $_SERVER['PHP_AUTH_USER'] ?? '';
    $password = $_SERVER['PHP_AUTH_PW'] ?? '';

    // ตรวจสอบการเข้าสู่ระบบ
    if ($username === $correct_username && $password === $correct_password) {
        // เชื่อมต่อฐานข้อมูล MySQL ด้วย PDO
        $pdo = new PDO("mysql:host=$db_host;dbname=$db_name;charset=utf8", $db_user, $db_pass);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

        // รับ parameter วันที่ (default = วันนี้ + เมื่อวาน)
        $date = $_GET['date'] ?? null;
        $date_from = $_GET['date_from'] ?? null;
        $date_to = $_GET['date_to'] ?? null;

        if ($date_from && $date_to) {
            $stmt = $pdo->prepare("SELECT * FROM leave_requests WHERE DATE(created_at) BETWEEN ? AND ?");
            $stmt->execute([$date_from, $date_to]);
        } elseif ($date) {
            $stmt = $pdo->prepare("SELECT * FROM leave_requests WHERE DATE(created_at) = ?");
            $stmt->execute([$date]);
        } else {
            // default = ย้อนหลัง 30 วัน
            $date_to = date('Y-m-d');
            $date_from = date('Y-m-d', strtotime('-30 days'));
            $stmt = $pdo->prepare("SELECT * FROM leave_requests WHERE DATE(created_at) BETWEEN ? AND ?");
            $stmt->execute([$date_from, $date_to]);
        }
        $leave_records = $stmt->fetchAll(PDO::FETCH_ASSOC);

        // สร้าง array ที่จะใช้แปลงเป็น JSON
        $data_to_send = [];

        // 📌 เพิ่ม employee_code ใน query
        $user_stmt = $pdo->prepare("SELECT firstname, lastname, branch, employee_code FROM users WHERE id = ?");

        foreach ($leave_records as $record) {
            $approved_by_name = null;
            $user_branch = null;
            $employee_code = null;

            // 📌 ดึง branch + employee_code จากตาราง users
            if (!empty($record['user_id'])) {
                $user_stmt->execute([$record['user_id']]);
                $user = $user_stmt->fetch(PDO::FETCH_ASSOC);

                if ($user) {
                    $user_branch = $user['branch'];
                    $employee_code = $user['employee_code'];
                }
            }

            // 📌 ดึงชื่อผู้อนุมัติ
            if (!empty($record['approved_by'])) {
                $user_stmt->execute([$record['approved_by']]);
                $approver = $user_stmt->fetch(PDO::FETCH_ASSOC);

                if ($approver) {
                    $approved_by_name = $approver['firstname'] . ' ' . $approver['lastname'];
                }
            }

            $data_to_send[] = [
                'id' => $record['id'],
                'user_id' => (string)$record['user_id'],
                'employee_code' => $employee_code,
                'username' => $record['username'],
                'leave_start_date' => $record['leave_start_date'],
                'leave_start_time' => $record['leave_statr_time'],
                'leave_end_date' => $record['leave_end_date'],
                'leave_end_time' => $record['leave_end_time'],
                'leave_type' => $record['leave_type'],
                'note' => $record['note'],
                'file_path' => $record['file_path'],
                'state' => $record['state'],
                'reason' => $record['reason'],
                'approved_by' => $approved_by_name,
                'branch' => $user_branch,
                'department' => $record['department'],
                'position' => $record['position'],
                'created_at' => $record['created_at'],
                'company' => !empty($record['company']) ? $record['company'] : 'ไม่ระบุบริษัท',
            ];
        }

        // แปลง array เป็น JSON และแสดงผล
        echo json_encode($data_to_send);

    } else {
        http_response_code(401);
        header('WWW-Authenticate: Basic realm="My API"');
        echo json_encode(['error' => "Unauthorized access. Invalid credentials."]);
    }

} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['error' => "ข้อผิดพลาดในการเชื่อมต่อ MySQL: " . $e->getMessage()]);
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['error' => "ข้อผิดพลาดทั่วไป: " . $e->getMessage()]);
}
?>
