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
            $stmt = $pdo->prepare("SELECT * FROM manual_time_logs WHERE DATE(created_at) BETWEEN ? AND ?");
            $stmt->execute([$date_from, $date_to]);
        } elseif ($date) {
            $stmt = $pdo->prepare("SELECT * FROM manual_time_logs WHERE DATE(created_at) = ?");
            $stmt->execute([$date]);
        } else {
            // ไม่ส่ง = วันนี้
            $today = date('Y-m-d');
            $stmt = $pdo->prepare("SELECT * FROM manual_time_logs WHERE DATE(created_at) = ?");
            $stmt->execute([$today]);
        }

        $time_logs = $stmt->fetchAll(PDO::FETCH_ASSOC);

        // สร้าง array ที่จะใช้แปลงเป็น JSON
        $data_to_send = [];

        // 📌 เตรียม Prepared Statement สำหรับค้นหา user ไว้ก่อนลูป
        $user_stmt = $pdo->prepare("SELECT firstname, lastname, branch, employee_code FROM users WHERE id = ?");

        foreach ($time_logs as $log) {
            $approved_by_name = null;
            $user_branch = null;

            // ดึง branch + employee_code จากตาราง users โดยใช้ user_id
            $employee_code = null;
            if (!empty($log['user_id'])) {
                $user_stmt->execute([$log['user_id']]);
                $user = $user_stmt->fetch(PDO::FETCH_ASSOC);

                if ($user) {
                    $user_branch = $user['branch'];
                    $employee_code = $user['employee_code'];
                }
            }

            if (!empty($log['approved_by'])) {
                $user_stmt->execute([$log['approved_by']]);
                $user = $user_stmt->fetch(PDO::FETCH_ASSOC);
                if ($user) {
                    $approved_by_name = $user['firstname'] . ' ' . $user['lastname'];
                }
            }

            $data_to_send[] = [
                'hr_id_manual_time_log' => (string)$log['id'],
                'user_id' => (string)$log['user_id'],
                'employee_code' => $employee_code,
                'username' => $log['username'],
                'work_date' => $log['work_date'],
                'checkin_time' => $log['checkin_time'],
                'checkout_time' => $log['checkout_time'],
                'branch' => $user_branch,
                'department' => $log['department'],
                'position' => $log['position'],
                'state' => $log['state'],
                'user_note' => $log['user_note'],
                'reason' => $log['reason'],
                'approved_by' => $approved_by_name,
                'approved_at' => $log['approved_at'],
                'created_at' => $log['created_at'],
                'company' => !empty($log['company']) ? $log['company'] : 'ไม่ระบุบริษัท',
                'reason_type' => $log['reason_type'],
                'allowance_type' => $log['allowance_type'] ?? null,
                'amount' => $log['amount'] ?? null,
                'file_path' => $log['file_path'] ?? null
            ];
        }

        // แปลง array เป็น JSON และแสดงผล
        echo json_encode($data_to_send);

    } else {
        // หากการตรวจสอบสิทธิ์ล้มเหลว
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
