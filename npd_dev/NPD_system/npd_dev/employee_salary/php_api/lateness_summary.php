<?php
// lateness_summary.php
define('DB_HOST', 'localhost');
define('DB_NAME', 'npdhr_dbbase_npd');
define('DB_USER', 'npdhr_dbbase_npd');
define('DB_PASS', '@Npd78901234');

$mysqli = new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME);
if ($mysqli->connect_error) {
    die("DB connection failed: " . $mysqli->connect_error);
}

header("Content-Type: text/html; charset=utf-8");

// รับค่าจาก POST (JSON) หรือ GET
$input = file_get_contents('php://input');
$data  = json_decode($input, true);

$employee_code = $data['employee_code'] ?? $_GET['employee_code'] ?? '';
$month  = (int)($data['month'] ?? $_GET['month'] ?? date('m'));
$year   = (int)($data['year'] ?? $_GET['year'] ?? date('Y'));
$cutoff = (int)($data['cutoff_day'] ?? $_GET['cutoff_day'] ?? 24);

// ============================================================
// ✅ Helper: คำนวณนาทีที่ทับซ้อนช่วงพักเที่ยง 12:00-13:00
// ============================================================
function getLunchOverlapMinutes($start_dt, $end_dt) {
    if (!$start_dt || !$end_dt) return 0;
    if ($end_dt <= $start_dt) return 0;
    $date_str = $start_dt->format('Y-m-d');
    $lunch_start = new DateTime("$date_str 12:00:00");
    $lunch_end   = new DateTime("$date_str 13:00:00");
    $overlap_start = max($start_dt->getTimestamp(), $lunch_start->getTimestamp());
    $overlap_end   = min($end_dt->getTimestamp(), $lunch_end->getTimestamp());
    if ($overlap_start < $overlap_end) {
        return ($overlap_end - $overlap_start) / 60;
    }
    return 0;
}

// ============================================================
// ✅ Helper: คำนวณนาทีที่ช่วง [a_start, a_end] ทับซ้อนกับ [b_start, b_end]
//    ใช้กัน "หักซ้ำ/แสดงซ้ำ" ระหว่าง สาย/ออกก่อนเวลา กับ ช่วงเวลาลา
// ============================================================
function getOverlapMinutes($a_start, $a_end, $b_start, $b_end) {
    if (!$a_start || !$a_end || !$b_start || !$b_end) return 0;
    $s = max($a_start->getTimestamp(), $b_start->getTimestamp());
    $e = min($a_end->getTimestamp(),   $b_end->getTimestamp());
    return ($s < $e) ? ($e - $s) / 60 : 0;
}

// ✅ แปลง Float ชั่วโมง (จาก hr.work.schedule) → "HH:MM:00"
//    7.0→07:00  7.5→07:30  16.0→16:00  8.25→08:15
function floatHourToTime($v) {
    $v = (float)$v;
    $h = (int)floor($v);
    $m = (int)round(($v - $h) * 60);
    if ($m >= 60) { $h += 1; $m -= 60; }
    return sprintf("%02d:%02d:00", $h, $m);
}


// ==========================
// หา user_id จาก users
// ==========================
$resUser = $mysqli->query("
    SELECT id, employee_code, username, firstname, lastname
    FROM users
    WHERE employee_code='{$employee_code}'
    LIMIT 1
");

if (!$resUser || !$resUser->num_rows) {
    echo "<h2 style='color:red'>❌ ไม่พบพนักงานรหัส {$employee_code}</h2>";
    exit();
}

$userRow = $resUser->fetch_assoc();
$user_id   = (int)$userRow['id'];
$fullname  = trim($userRow['firstname']." ".$userRow['lastname']);


// ==========================
// คำนวณช่วงเวลา
// ==========================
$end   = new DateTime("$year-$month-$cutoff");
$start = (clone $end)->modify('-1 month')->modify('+1 day');
$start_date = $start->format('Y-m-d 00:00:00');
$end_date   = $end->format('Y-m-d 23:59:59');

// ============================================================
// ✅ Helper: ดึง "ช่วงเวลาลาที่อนุมัติ" ของวันหนึ่ง (ใช้กันแสดง สาย/ขาด ซ้ำกับช่วงลา)
// ============================================================
function getApprovedLeaveIntervals($mysqli, $user_id, $wd) {
    $intervals = [];
    $q = $mysqli->query("SELECT leave_statr_time, leave_end_time FROM leave_requests
                         WHERE user_id={$user_id} AND state='อนุมัติ'
                           AND ('{$wd}' BETWEEN DATE(leave_start_date) AND DATE(leave_end_date))");
    if ($q) {
        while ($lv = $q->fetch_assoc()) {
            if (empty($lv['leave_statr_time']) || empty($lv['leave_end_time'])) continue;
            $intervals[] = [
                new DateTime("{$wd} ".$lv['leave_statr_time']),
                new DateTime("{$wd} ".$lv['leave_end_time'])
            ];
        }
    }
    return $intervals;
}
?>
<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <title>สรุปการขาด ลา มาสาย</title>
  <style>
    body { font-family: Tahoma, sans-serif; font-size: 14px; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 30px; }
    th, td { border: 1px solid #999; padding: 6px 10px; text-align: left; }
    th { background: #f2f2f2; }
    h2 { margin-top: 40px; }
  </style>
</head>
<body>

<h1>📊 รายงานการขาด ลา มาสาย</h1>
<p>พนักงาน: <?= htmlspecialchars($fullname) ?> (รหัส <?= $employee_code ?>)</p>
<p>ช่วงวันที่: <?= $start->format('d/m/Y') ?> - <?= $end->format('d/m/Y') ?></p>

<?php
// ==========================
// ตาราง checkin_logs
// ==========================
echo "<h2>✔️ เข้างาน/ออกงาน</h2>";
$sql = "SELECT * FROM checkin_logs
        WHERE user_id={$user_id}
          AND checked_at BETWEEN '$start_date' AND '$end_date'
        ORDER BY checked_at ASC";
$res = $mysqli->query($sql);

if ($res && $res->num_rows > 0) {
    echo "<table><tr>
           <th>ชื่อ</th><th>สาขา</th>
            <th>ประเภท</th><th>วันที่ลงเวลา</th>
            <th>แผนก</th><th>ตำแหน่ง</th>
            <th>ละติจูด</th><th>ลองจิจูด</th>
            <th>สถานะ ขาด/สาย</th>
          </tr>";

    while ($row = $res->fetch_assoc()) {
        $status = "<span style='color:green'>ปกติ</span>"; // ค่า default
        $checked_at = new DateTime($row['checked_at']);
        $dow = strtolower($checked_at->format('D')); // mon, tue, wed ...

        // ✅ manual_time_log ประเภท "ถือว่ามาทำงานจริง" อนุมัติแล้ว → OVERRIDE เวลาที่ใช้คำนวณ สาย/ขาด
        //    รวม: ลืมลงเวลา / ทำงานนอกสถานที่ / ระบบมีปัญหา
        //    (ไม่รวม ค่าเบี้ยเลี้ยงออกนอกสถานที่ = OT/เบี้ยเลี้ยง เงิน ไม่ใช่เวลาทำงาน)
        //    ให้ตรงกับ calculate_lateness.php (MIN checkin / MAX checkout ของวันนั้น)
        $wd = $checked_at->format('Y-m-d');
        $qman = $mysqli->query("SELECT MIN(checkin_time) AS ci, MAX(checkout_time) AS co
                                FROM manual_time_logs
                                WHERE user_id={$user_id} AND work_date='{$wd}'
                                  AND reason_type IN ('ลืมลงเวลา','ทำงานนอกสถานที่','ระบบมีปัญหา')
                                  AND state='อนุมัติ'");

        if ($qman && ($mrow = $qman->fetch_assoc())) {
            if ($row['check_type'] === 'in'  && !empty($mrow['ci'])) {
                $checked_at = new DateTime("{$wd} ".$mrow['ci']);
            }
            if ($row['check_type'] === 'out' && !empty($mrow['co'])) {
                $checked_at = new DateTime("{$wd} ".$mrow['co']);
            }
        }

        // ✅ ช่วงเวลาลาที่อนุมัติของวันนั้น → ใช้กันแสดง สาย/ขาด ซ้ำกับช่วงลา
        $leave_intervals = getApprovedLeaveIntervals($mysqli, $user_id, $wd);

        // ✅ เอา shift ของวันนั้นจาก work_schedule ที่ Odoo ส่งมา
        if (!empty($_GET['work_schedule'])) {
            $schedule_data = json_decode($_GET['work_schedule'], true);
            if (!empty($schedule_data[$dow]) && $schedule_data[$dow] !== "0-0") {
                list($shift_start, $shift_end) = explode("-", $schedule_data[$dow]);

                $shift_start_dt = new DateTime($checked_at->format("Y-m-d")." ".floatHourToTime($shift_start));
                $shift_end_dt   = new DateTime($checked_at->format("Y-m-d")." ".floatHourToTime($shift_end));


                $grace_min = isset($_GET['lateness_grace_period']) ? (int)$_GET['lateness_grace_period'] : 0;

                if ($row['check_type'] === "in") {
                    // มาสาย = เวลาเข้าเกิน shift_start + grace
                    $limit = clone $shift_start_dt;
                    $limit->modify("+{$grace_min} minutes");

                    // ✅ ตัดวินาทีออก (ใช้แค่ ชม:นาที)
                    $checked_at_trimmed = new DateTime($checked_at->format("Y-m-d H:i"));

                    if ($checked_at_trimmed > $limit) {
                        // ✅ คำนวณเป็นนาที → หักพักเที่ยง → กันทับซ้อนช่วงลา → แปลงกลับเป็น ชม/นาที
                        $total_min = ($checked_at_trimmed->getTimestamp() - $shift_start_dt->getTimestamp()) / 60;
                        $total_min -= getLunchOverlapMinutes($shift_start_dt, $checked_at_trimmed);
                        foreach ($leave_intervals as $iv) {
                            $total_min -= getOverlapMinutes($shift_start_dt, $checked_at_trimmed, $iv[0], $iv[1]);
                        }
                        $total_min = max(0, (int)$total_min);
                        if ($total_min > 0) {
                            $h = intdiv($total_min, 60);
                            $m = $total_min % 60;
                            $status = "<span style='color:red'>สาย {$h}ชม {$m}นาที</span>";
                        } elseif (!empty($leave_intervals)) {
                            // เข้าสายเพราะอยู่ในช่วงลา → ไม่คิดสาย
                            $status = "<span style='color:#2196F3'>ลา (ช่วงเช้า)</span>";
                        }
                    }
                } elseif ($row['check_type'] === "out") {
                    // ✅ ตัดวินาทีออก (ใช้แค่ ชม:นาที)
                    $checked_at_trimmed = new DateTime($checked_at->format("Y-m-d H:i"));

                    // ขาด = เวลาออกก่อนเวลาเลิกงาน
                    if ($checked_at_trimmed < $shift_end_dt) {
                        // ✅ คำนวณเป็นนาที → หักพักเที่ยง → กันทับซ้อนช่วงลา → แปลงกลับเป็น ชม/นาที
                        $total_min = ($shift_end_dt->getTimestamp() - $checked_at_trimmed->getTimestamp()) / 60;
                        $total_min -= getLunchOverlapMinutes($checked_at_trimmed, $shift_end_dt);
                        foreach ($leave_intervals as $iv) {
                            $total_min -= getOverlapMinutes($checked_at_trimmed, $shift_end_dt, $iv[0], $iv[1]);
                        }
                        $total_min = max(0, (int)ceil($total_min));
                        if ($total_min > 0) {
                            $h = intdiv($total_min, 60);
                            $m = $total_min % 60;
                            $status = "<span style='color:orange'>ขาด {$h}ชม {$m}นาที</span>";
                        } elseif (!empty($leave_intervals)) {
                            // ออกก่อนเวลาเพราะอยู่ในช่วงลา → ไม่คิดขาด
                            $status = "<span style='color:#2196F3'>ลา (ช่วงบ่าย)</span>";
                        }
                    }
                }

            }
        }

        echo "<tr>
                <td>{$row['username']}</td>
                <td>{$row['branch']}</td>
                <td>{$row['check_type']}</td>
                <td>{$row['checked_at']}</td>
                <td>{$row['department']}</td>
                <td>{$row['position']}</td>
                <td>{$row['latitude']}</td>
                <td>{$row['longitude']}</td>
                <td>{$status}</td>
              </tr>";
    }
    echo "</table>";
} else {
    echo "<p>❌ ไม่มีข้อมูล เข้างาน/ออกงาน</p>";
}


// ==========================
// ตาราง leave_requests
// ==========================
echo "<h2>📝 ลา</h2>";
$sql = "SELECT * FROM leave_requests
        WHERE user_id={$user_id}
          AND (
            (leave_start_date BETWEEN '{$start->format('Y-m-d')}' AND '{$end->format('Y-m-d')}')
            OR
            (leave_end_date BETWEEN '{$start->format('Y-m-d')}' AND '{$end->format('Y-m-d')}')
          )
        ORDER BY leave_start_date ASC";

$res = $mysqli->query($sql);
if ($res && $res->num_rows > 0) {
    echo "<table><tr>
            <th>ชื่อ</th><th>วันที่เริ่มต้น</th><th>เวลาเริ่มต้น</th>
            <th>วันที่สิ้นสุด</th><th>เวลาสิ้นสุด</th>
            <th>ประเภทการลา</th><th>สถานะ</th><th>ไฟล์</th>
          </tr>";
    while ($row = $res->fetch_assoc()) {
        $file_link = !empty($row['file_path'])
            ? "<a href='https://npdhrms.com/{$row['file_path']}' target='_blank'>📂 เปิดไฟล์</a>"
            : "-";

        echo "<tr>
                <td>{$row['username']}</td>
                <td>{$row['leave_start_date']}</td>
                <td>{$row['leave_statr_time']}</td>
                <td>{$row['leave_end_date']}</td>
                <td>{$row['leave_end_time']}</td>
                <td>{$row['leave_type']}</td>
                <td>{$row['state']}</td>
                <td>{$file_link}</td>
              </tr>";
    }
    echo "</table>";
} else {
    echo "<p>❌ ไม่มีข้อมูล ลา</p>";
}


// ==========================
// ตาราง manual_time_logs
// ==========================
echo "<h2>⏱️ เพิ่มเวลา</h2>";
$sql = "SELECT * FROM manual_time_logs
        WHERE user_id={$user_id}
          AND work_date BETWEEN '{$start->format('Y-m-d')}' AND '{$end->format('Y-m-d')}'
        ORDER BY work_date ASC";
$res = $mysqli->query($sql);
if ($res && $res->num_rows > 0) {
    echo "<table><tr>
           <th>ชื่อ</th><th>วันที่ขอเพิ่มเวลา</th>
            <th>เวลาเริ่ม</th><th>เวลาสิ้นสุด</th>
            <th>ประเภทการเพิ่มเวลา</th><th>สถานะ</th><th>ไฟล์</th>
          </tr>";
    while ($row = $res->fetch_assoc()) {
        $file_link = !empty($row['file_path'])
            ? "<a href='https://npdhrms.com/api/{$row['file_path']}' target='_blank'>📂 เปิดไฟล์</a>"
            : "-";

        echo "<tr>
                <td>{$row['username']}</td>
                <td>{$row['work_date']}</td>
                <td>{$row['checkin_time']}</td>
                <td>{$row['checkout_time']}</td>
                <td>{$row['reason_type']}</td>
                <td>{$row['state']}</td>
                <td>{$file_link}</td>
              </tr>";
    }
    echo "</table>";
} else {
    echo "<p>❌ ไม่มีข้อมูล เพิ่มเวลา</p>";
}

$mysqli->close();
?>

</body>
</html>
