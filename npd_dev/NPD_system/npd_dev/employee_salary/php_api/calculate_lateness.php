<?php
// Database connection
define('DB_HOST', 'localhost');
define('DB_NAME', 'npdhr_dbbase_npd');
define('DB_USER', 'npdhr_dbbase_npd');
define('DB_PASS', '@Npd78901234');

header('Content-Type: application/json');
$mysqli = new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME);
if ($mysqli->connect_error) {
    die(json_encode(['status'=>'error','message'=>'DB connection failed: '.$mysqli->connect_error]));
}

$input = file_get_contents('php://input');
$data  = json_decode($input, true);

$employee_code = $mysqli->real_escape_string($data['employee_code']);
$grace_period  = (int)($data['grace_period'] ?? 15);
$work_schedule = $data['work_schedule'] ?? [];
$month         = (int)($data['month'] ?? date('m'));
$year          = (int)($data['year'] ?? date('Y'));
$cutoff_day    = (int)($data['cutoff_day'] ?? 24);

// normalize holidays
$holidays = array_map(function($h) {
    return (new DateTime($h))->format('Y-m-d');
}, $data['official_holidays'] ?? []);

// ✅ วันที่ลาออก (จาก payload) — ไม่นับวันหลังลาออกเป็นขาดงาน
$resign_date = null;
if (!empty($data['resign_date'])) {
    try {
        $resign_date = (new DateTime($data['resign_date']))->setTime(0, 0, 0);
    } catch (Exception $e) {
        $resign_date = null;
    }
}

// หา user_id + salary + start_date
$resUser = $mysqli->query("SELECT id, salary, start_date FROM users WHERE employee_code='{$employee_code}' LIMIT 1");
if (!$resUser || !$resUser->num_rows) {
    echo json_encode(['status'=>'error','message'=>"ไม่พบพนักงานรหัส {$employee_code}"]);
    exit();
}
$userRow = $resUser->fetch_assoc();
$user_id = $userRow['id'];
$salary_per_month = (float)$userRow['salary'];

// ✅ วันที่เริ่มงาน (จากตาราง users) — ไม่นับวันก่อนเริ่มงานเป็นขาดงาน
$start_work = null;
if (!empty($userRow['start_date']) && $userRow['start_date'] !== '0000-00-00') {
    try {
        $start_work = (new DateTime($userRow['start_date']))->setTime(0, 0, 0);
    } catch (Exception $e) {
        $start_work = null;
    }
}

$end = new DateTime("$year-$month-$cutoff_day");
$start = (clone $end)->modify('-1 month')->modify('+1 day');

$start_date = $start->format('Y-m-d 00:00:00');
$end_date   = $end->format('Y-m-d 23:59:59');

$total_lateness   = 0;
$total_late_in    = 0;
$total_early_out  = 0;
$working_days     = 0;
$holiday_days     = 0;
$present_days     = 0;
$leave_deduction_total = 0;

$missed_days_log  = [];
$late_log         = [];
$early_log        = [];
$leave_log        = [];

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
//    ใช้กัน "หักซ้ำ" ระหว่าง สาย/ออกก่อนเวลา กับ ช่วงเวลาลา
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

// ฟังก์ชันคำนวณเงินหักจากการลา
function calculateLeaveDeduction($salary_per_month, $shift_start, $shift_end, $leave_start, $leave_end) {
    $daily_rate = $salary_per_month / 30;

    // ✅ ชั่วโมงทำงานจริงในกะ (หักพักเที่ยงถ้ากะคาบ 12:00-13:00)
    $total_working_hours = ($shift_end->getTimestamp() - $shift_start->getTimestamp()) / 3600;
    $shift_lunch_hours   = getLunchOverlapMinutes($shift_start, $shift_end) / 60;
    $total_working_hours -= $shift_lunch_hours;
    if ($total_working_hours <= 0) $total_working_hours = 8; // fallback

    // ถ้าลาครอบคลุมทั้งกะ → หักเต็มวัน
    if ($leave_start <= $shift_start && $leave_end >= $shift_end) {
        return round($daily_rate, 2);
    }

    // ✅ คิดเป็น "นาที" ตามจริง — ไม่ปัดขึ้นเป็นชั่วโมงเต็ม
    //    เช่น ลา 10:00-10:37 = 37 นาที → หัก 37 × ค่าจ้างต่อนาที (ไม่ใช่ปัดเป็น 1 ชม.)
    //    (ให้สอดคล้องกับ สาย/ออกก่อนเวลา ที่คิดเป็นนาทีอยู่แล้ว)
    $minutes_leave = ($leave_end->getTimestamp() - $leave_start->getTimestamp()) / 60;
    $leave_lunch_minutes = getLunchOverlapMinutes($leave_start, $leave_end); // หักพักเที่ยงถ้าลาคาบ 12:00-13:00
    $minutes_leave -= $leave_lunch_minutes;
    if ($minutes_leave < 0) $minutes_leave = 0;

    $hourly_rate = $daily_rate / $total_working_hours;
    $minute_rate = $hourly_rate / 60;
    // ✅ ปัดทีละใบ 2 ตำแหน่ง ให้ยอดรวม (field) ตรงกับตารางแจกแจง (ที่ปัดทีละบรรทัด)
    return round($minute_rate * $minutes_leave, 2);
}

// ✅ เก็บ "วันนี้" ตอน 00:00:00 ไว้เปรียบเทียบ
$today = (new DateTime())->setTime(0, 0, 0);

$cursor = clone $start;
while ($cursor <= $end) {
    $d = $cursor->format('Y-m-d');
    $dow = strtolower($cursor->format('D'));

    // ✅ skip วันที่ยังมาไม่ถึง (วันนี้ + อนาคต)
    if ($cursor >= $today) {
        $cursor->modify('+1 day');
        continue;
    }

    // ✅ skip วันก่อนเริ่มงาน — ยังไม่เป็นพนักงาน ไม่นับเป็นขาดงาน
    if ($start_work !== null && $cursor < $start_work) {
        $cursor->modify('+1 day');
        continue;
    }

    // ✅ skip วันหลังลาออก — ลาออกแล้ว ไม่ใช่ขาด
    if ($resign_date !== null && $cursor > $resign_date) {
        $cursor->modify('+1 day');
        continue;
    }

    $work_key       = "work_{$dow}";
    $shift_start_key= "{$dow}_shift_start";
    $shift_end_key  = "{$dow}_shift_end";

    if (!empty($work_schedule[$work_key])) {
        if (in_array($d, $holidays)) {
            $holiday_days++;
            $cursor->modify('+1 day');
            continue;
        }

        $working_days++;

        $shift_start = new DateTime("$d " . floatHourToTime($work_schedule[$shift_start_key] ?? 8));
        $shift_end   = new DateTime("$d " . floatHourToTime($work_schedule[$shift_end_key] ?? 17));

        // ============================================================
        // ✅ ดึง "ทุกใบลาที่อนุมัติ" ของวันนี้ (เดิมดึงแค่ใบเดียว LIMIT 1)
        //    - คิดเงินหักจากการลา (เฉพาะประเภทที่หักจริง)
        //    - เก็บ "ช่วงเวลาลา" ทุกใบ เพื่อนำไปกัน "หักซ้ำ" สาย/ออกก่อนเวลา
        // ============================================================
        $qleave = $mysqli->query("
            SELECT * FROM leave_requests
            WHERE user_id='$user_id' AND state='อนุมัติ'
              AND ('$d' BETWEEN DATE(leave_start_date) AND DATE(leave_end_date))
            ORDER BY leave_statr_time ASC
        ");
        $leaves = [];
        if ($qleave) { while ($lr = $qleave->fetch_assoc()) { $leaves[] = $lr; } }

        $leave_intervals    = [];     // [[DateTime start, DateTime end], ...] กันหักซ้ำ
        $day_fully_on_leave = false;  // ลาครอบคลุมทั้งกะ
        $count_as_present   = false;

        foreach ($leaves as $leave) {
            $leave_start = new DateTime("$d ".$leave['leave_statr_time']);   // ← leave_statr_time (สะกดตามตาราง)
            $leave_end   = new DateTime("$d ".$leave['leave_end_time']);
            $type        = $leave['leave_type'];
            $file_path   = $leave['file_path'];

            $deduct = 0;
            switch ($type) {
                case 'ลากิจไม่ได้รับค่าจ้าง':
                    $deduct = calculateLeaveDeduction($salary_per_month,$shift_start,$shift_end,$leave_start,$leave_end);
                    break;

                case 'ลากิจได้รับค่าจ้าง':
                    $count_as_present = true; // ไม่หัก
                    break;

                case 'ลาป่วยมีใบรับรองแพทย์':
                    if (!empty($file_path)) {
                        $count_as_present = true;
                    } else {
                        $deduct = calculateLeaveDeduction($salary_per_month,$shift_start,$shift_end,$leave_start,$leave_end);
                    }
                    break;

                case 'ลาคลอดได้รับค่าจ้าง':
                case 'ลาพักร้อน':
                case 'สิทธิหยุดวันเสาร์':
                case 'ฉุกเฉิน':
                    $count_as_present = true;
                    break;

                case 'ลาคลอดไม่ได้รับค่าจ้าง':
                    $deduct = calculateLeaveDeduction($salary_per_month,$shift_start,$shift_end,$leave_start,$leave_end);
                    break;
            }

            if ($deduct > 0) {
                $leave_deduction_total += $deduct;
                $leave_log[] = [
                    'date'=>$d,
                    'type'=>$type,
                    'deduction'=>$deduct,
                    'start'=>$leave_start->format('H:i'),   // เวลาเริ่มลา
                    'end'=>$leave_end->format('H:i'),       // เวลาสิ้นสุดลา
                ];
            }

            // ✅ ทุกใบลาที่อนุมัติ → ช่วงเวลานี้ "ไม่คิดเป็น สาย/ออกก่อนเวลา" (กันหักซ้ำ)
            $leave_intervals[] = [$leave_start, $leave_end];

            // ลาครอบคลุมทั้งกะ → ทั้งวันเป็นวันลา
            if ($leave_start <= $shift_start && $leave_end >= $shift_end) {
                $day_fully_on_leave = true;
            }
        }

        // ✅ ลาครอบคลุมทั้งกะ → ไม่ต้องคิดเช็คเข้า-ออก (เหมือนเดิม: ทั้งวันเป็นวันลา)
        if ($day_fully_on_leave) {
            if ($count_as_present) $present_days++;
            $cursor->modify('+1 day');
            continue;
        }

        // ============================================================
        // เช็คเข้า-ออก (วันทำงานปกติ หรือ วันที่ลาเพียง "บางช่วง")
        // ============================================================
        $qin = $mysqli->query("SELECT checked_at FROM checkin_logs
                               WHERE user_id='$user_id' AND check_type='in'
                               AND DATE(checked_at)='$d' ORDER BY checked_at ASC LIMIT 1");
        $qout= $mysqli->query("SELECT checked_at FROM checkin_logs
                               WHERE user_id='$user_id' AND check_type='out'
                               AND DATE(checked_at)='$d' ORDER BY checked_at DESC LIMIT 1");

        $checkin  = ($qin && $qin->num_rows)? new DateTime($qin->fetch_assoc()['checked_at']) : null;
        $checkout = ($qout&& $qout->num_rows)? new DateTime($qout->fetch_assoc()['checked_at']): null;

        // ✅ manual_time_log 'ลืมลงเวลา' ที่อนุมัติแล้ว → OVERRIDE checkin_logs
        $qman = $mysqli->query("SELECT MIN(checkin_time) AS ci, MAX(checkout_time) AS co
                                FROM manual_time_logs
                                WHERE user_id='$user_id' AND work_date='$d'
                                  AND reason_type = 'ลืมลงเวลา'
                                  AND state='อนุมัติ'");

        if ($qman && ($row = $qman->fetch_assoc())) {
            if (!empty($row['ci'])) $checkin  = new DateTime("$d ".$row['ci']);
            if (!empty($row['co'])) $checkout = new DateTime("$d ".$row['co']);
        }

        if ($checkin && $checkout) {
            $present_days++;

            // ✅ เข้าสาย — คิด "นาทีดิบ" ก่อน → หักพักเที่ยง + กันทับซ้อนช่วงลา → แล้วค่อย floor
            //    (ต้องหักก่อนปัด ไม่งั้นจะเหลือเศษนาทีค้างจากการปัด)
            $lateRaw = ($checkin->getTimestamp() - $shift_start->getTimestamp())/60;
            $lateMin = 0;
            if ($lateRaw > 0) {
                $lateRaw -= getLunchOverlapMinutes($shift_start, $checkin);
                // ตัดนาทีที่ทับซ้อนช่วงลาออก (เช่น ลาช่วงเช้า → เข้าสายเพราะลา ไม่หักซ้ำ)
                foreach ($leave_intervals as $iv) {
                    $lateRaw -= getOverlapMinutes($shift_start, $checkin, $iv[0], $iv[1]);
                }
                $lateMin = max(0, (int)floor(round($lateRaw, 6)));
            }
            if ($lateMin > $grace_period) {
                $total_lateness += $lateMin;
                $total_late_in  += $lateMin;
                $late_log[] = [
                    'date'=>$d,
                    'minutes'=>$lateMin,
                    'checkin'=>$checkin->format('H:i'),         // เวลาเข้าจริง
                    'shift_start'=>$shift_start->format('H:i'), // เวลากะเริ่ม
                ];
            }

            // ✅ ออกก่อนเวลา — คิด "นาทีดิบ" ก่อน → หักพักเที่ยง + กันทับซ้อนช่วงลา → แล้วค่อย ceil
            //    (ต้องหักก่อนปัด ไม่งั้น 18/05 ออก 15:00:31 ลา 15:00-17:00 จะเหลือเศษ ~0.5 นาที
            //     แล้วถูกปัดเป็น 1 บาท ทั้งที่ออกในช่วงลา = ไม่ควรหัก)
            if ($checkout < $shift_end) {
                $earlyRaw = ($shift_end->getTimestamp() - $checkout->getTimestamp())/60;
                $earlyRaw -= getLunchOverlapMinutes($checkout, $shift_end);
                // ตัดนาทีที่ทับซ้อนช่วงลาออก (เช่น 30/04 ลา 15:00-17:00 + ออก 15:02
                //  → ออกก่อนเวลา 15:02-17:00 ทับช่วงลาเต็ม → เหลือ 0, หักเฉพาะ "ลา")
                foreach ($leave_intervals as $iv) {
                    $earlyRaw -= getOverlapMinutes($checkout, $shift_end, $iv[0], $iv[1]);
                }
                $earlyMin = max(0, (int)ceil(round($earlyRaw, 6)));
                if ($earlyMin > 0) {
                    $total_lateness += $earlyMin;
                    $total_early_out+= $earlyMin;
                    $early_log[] = [
                        'date'=>$d,
                        'minutes'=>$earlyMin,
                        'checkout'=>$checkout->format('H:i'),   // เวลาออกจริง
                        'shift_end'=>$shift_end->format('H:i'), // เวลากะเลิก
                    ];
                }
            }
        } else {
            // ✅ ไม่มีเช็คเข้า-ออกครบ
            //    - ถ้าวันนั้นมีใบลา (บางช่วง) → ไม่นับเป็นขาด (ให้ประโยชน์วันที่มีใบลา)
            //    - ถ้าไม่มีใบลาเลย → ขาดงานเต็มวัน
            if (empty($leaves)) {
                $missed_days_log[] = $d;
            }
        }
    }

    $cursor->modify('+1 day');
}

// missed days
$missed_days = count($missed_days_log);

// คำนวณค่าจ้างรายวันและรายนาที
$daily_rate  = $salary_per_month / 30;
$total_shift_hours = 0;
$total_working_days_with_schedule = 0;

foreach (['mon','tue','wed','thu','fri','sat','sun'] as $dow) {
    $work_key = "work_{$dow}";
    $shift_start_key = "{$dow}_shift_start";
    $shift_end_key   = "{$dow}_shift_end";

    if (!empty($work_schedule[$work_key])) {
        $start_hour = (float)($work_schedule[$shift_start_key] ?? 8);
        $end_hour   = (float)($work_schedule[$shift_end_key] ?? 17);
        $hours = $end_hour - $start_hour;

        // ❗ หักพักเที่ยง 1 ชั่วโมง ถ้าเป็นกะเต็มวัน (>= 8 ชั่วโมง)
        if ($hours >= 8) {
            $hours -= 1;
        }

        $total_shift_hours += $hours;
        $total_working_days_with_schedule++;
    }
}

$avg_shift_hours = $total_working_days_with_schedule > 0
    ? $total_shift_hours / $total_working_days_with_schedule
    : 8;

$daily_rate  = $salary_per_month / 30;
$hourly_rate = $daily_rate / $avg_shift_hours;
$minute_rate = $hourly_rate / 60;

$deduction_absent  = $missed_days * $daily_rate;
$early_checkout_deduction = round($total_early_out * $minute_rate, 2);
$deduction_absent_total = $deduction_absent + $early_checkout_deduction;

echo json_encode([
    'status'=>'success',
    'employee_code'=>$employee_code,
    'user_id'=>$user_id,
    'total_lateness_minutes'=>(int)$total_lateness,
    'total_late_checkin_minutes'=>(int)$total_late_in,
    'total_early_checkout_minutes'=>(int)$total_early_out,
    'missed_days'=>$missed_days,
    'working_days_count'=>$working_days,
    'holiday_days_count'=>$holiday_days,
    'leave_deduction_total'=>$leave_deduction_total,
    'deduction_absent'=>$deduction_absent,
    'early_checkout_deduction'=>$early_checkout_deduction,
    'deduction_absent_total'=>$deduction_absent_total,

    'debug'=>[
        'start_date'=>$start_date,
        'end_date'=>$end_date,
        'today'=>$today->format('Y-m-d'),
        'start_work'=>$start_work ? $start_work->format('Y-m-d') : null,
        'resign_date'=>$resign_date ? $resign_date->format('Y-m-d') : null,
        'missed_days_log'=>$missed_days_log,
        'late_checkin_log'=>$late_log,
        'early_checkout_log'=>$early_log,
        'leave_log'=>$leave_log,
        'holidays'=>$holidays
    ]
],JSON_UNESCAPED_UNICODE);

$mysqli->close();
?>
