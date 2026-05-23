<?php
// Set headers to return JSON
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *'); // Allow requests from any origin

// --- FOR DEBUGGING ONLY ---
// Uncomment the two lines below to display errors directly.
// Remember to comment them out again in production.
// ini_set('display_errors', 1);
// error_reporting(E_ALL);

// Database credentials
define('DB_HOST', 'localhost');
define('DB_NAME', 'npdhr_dbbase_npd');
define('DB_USER', 'npdhr_dbbase_npd');
define('DB_PASS', '@Npd78901234');

// Establish database connection
try {
    $pdo = new PDO("mysql:host=" . DB_HOST . ";dbname=" . DB_NAME, DB_USER, DB_PASS);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->exec("SET NAMES 'utf8'");
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['error' => 'Database connection failed: ' . $e->getMessage()]);
    exit();
}

// Get parameters from the request
$employee_code = isset($_GET['employee_code']) ? $_GET['employee_code'] : null;
$month = isset($_GET['month']) ? (int)$_GET['month'] : (int)date('m');
$year  = isset($_GET['year'])  ? (int)$_GET['year']  : (int)date('Y');
// ✅ วันตัดรอบ (จาก Odoo) — ใช้คำนวณรอบเงินเดือน 25–24 (default 24)
$cutoff_day = isset($_GET['cutoff_day']) ? (int)$_GET['cutoff_day'] : 24;

if (!$employee_code) {
    http_response_code(400);
    echo json_encode(['error' => 'Employee code is required.']);
    exit();
}

// ✅ ช่วงวันที่ตามรอบเงินเดือน = (วันตัดรอบเดือนก่อน + 1 วัน) ถึง (วันตัดรอบเดือนนี้)
//    เช่น month=5, cutoff_day=24 → 25/04 ถึง 24/05  (ให้ตรงกับ calculate_lateness.php)
$end   = new DateTime("$year-$month-$cutoff_day");
$start = (clone $end)->modify('-1 month')->modify('+1 day');
$start_date = $start->format('Y-m-d');
$end_date   = $end->format('Y-m-d');

// Prepare the SQL query
// เปลี่ยนจาก MONTH()/YEAR() (เดือนปฏิทิน) → BETWEEN ตามรอบเงินเดือน 25–24
$sql = "
    SELECT
        mtl.user_id,
        u.employee_code,
        mtl.work_date AS work_date,         -- วันที่ทำงานจริง
        mtl.checkin_time AS start_time,     -- เวลาเริ่มต้น
        mtl.checkout_time AS end_time,      -- เวลาสิ้นสุด
        mtl.created_at
    FROM
        manual_time_logs mtl
    JOIN
        users u ON mtl.user_id = u.id
    WHERE
        u.employee_code = :employee_code
        AND mtl.reason_type = 'ขอโอที'
        AND mtl.state = 'อนุมัติ'
        AND mtl.work_date BETWEEN :start_date AND :end_date
    ORDER BY mtl.work_date ASC
";

try {
    $stmt = $pdo->prepare($sql);
    $stmt->bindParam(':employee_code', $employee_code, PDO::PARAM_STR);
    $stmt->bindParam(':start_date', $start_date, PDO::PARAM_STR);
    $stmt->bindParam(':end_date', $end_date, PDO::PARAM_STR);
    $stmt->execute();

    $results = $stmt->fetchAll(PDO::FETCH_ASSOC);

    echo json_encode($results);

} catch (PDOException $e) {
    http_response_code(500);
    // Provide a more specific error message for easier debugging
    echo json_encode(['error' => 'SQL Query failed: ' . $e->getMessage()]);
}
?>
