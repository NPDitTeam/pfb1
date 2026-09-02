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
// ✅ ตั้ง charset ของ connection เป็น UTF-8 ไม่งั้นเงื่อนไขภาษาไทยใน WHERE (state='อนุมัติ',
//    leave_type, reason_type) จะ match ไม่ติด → ใบลา/บันทึกเวลาที่อนุมัติถูกมองข้าม → นับขาดงานผิด
$mysqli->set_charset('utf8mb4');

$input = file_get_contents('php://input');
$data  = json_decode($input, true);

$employee_code = $mysqli->real_escape_string($data['employee_code']);
$grace_period  = (int)($data['grace_period'] ?? 15);

// ✅ สูตรคิดสายที่ตั้งเองจาก Odoo (เมนู "กำหนดสูตรคิดสาย")
//    เป็นรายการที่มี effective_date กำกับ → เลือกใช้ตามวันที่ของแต่ละวัน
//    วันก่อนวันเริ่มใช้สูตรแรก ยังคิดด้วย $grace_period เดิม (ไม่กระทบยอดที่คำนวณไปแล้ว)
$lateness_rules = $data['lateness_rules'] ?? [];
if (!is_array($lateness_rules)) $lateness_rules = [];
// กันข้อมูลเพี้ยน: เก็บเฉพาะรายการที่เป็น array จริง ๆ
$lateness_rules = array_values(array_filter($lateness_rules, 'is_array'));
usort($lateness_rules, function ($a, $b) {
    return strcmp($a['effective_date'] ?? '', $b['effective_date'] ?? '');
});
// ✅ include_today: คิด "สายเข้างาน" ของวันนี้ด้วยไหม
//    payroll ไม่ส่ง (=false) -> พฤติกรรมเดิมเป๊ะ ยอดหักไม่ขยับระหว่างวัน
//    แอปมือถือส่ง true -> พนักงานเห็นว่าวันนี้สายกี่นาทีทันทีที่สแกนเข้า
$include_today = !empty($data['include_today']);

// ✅ include_pending_manual: นับคำขอเพิ่มเวลาที่ "ยังรออนุมัติ" เป็นการลงเวลาด้วยไหม
//    payroll ไม่ส่ง (=false) -> นับเฉพาะที่อนุมัติแล้ว เงินต้องอิงเอกสารที่อนุมัติจริง
//    การสแกนออกใบเตือนส่ง true -> คนที่มาทำงานจริงแต่ลืมกดแล้วยื่นคำขอไว้
//    จะไม่โดนใบเตือนระหว่างรออนุมัติ (ให้ประโยชน์แก่พนักงานไว้ก่อน)
$include_pending_manual = !empty($data['include_pending_manual']);
$manual_states = $include_pending_manual
    ? "'อนุมัติ','รออนุมัติ'"
    : "'อนุมัติ'";

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
// วันที่ "ไม่ได้สแกนเข้างานเลย" — ใช้เฉพาะการออกใบเตือน ไม่เกี่ยวกับการหักเงิน
// (ลืมสแกนออกอย่างเดียว ยังนับเป็นขาดในการหักเงินเหมือนเดิม แต่ไม่เอามาออกใบเตือน)
$missed_no_checkin_log = [];
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

// ============================================================
// ✅ Helper: หา "นาทีที่ผ่อนผันได้" ของวันนั้น จากสูตรที่ตั้งไว้ใน Odoo
//    $rules ต้องเรียงตาม effective_date จากเก่าไปใหม่แล้ว
//
//    - ไม่มีสูตรไหนครอบคลุมวันนี้ -> คืน $default (สูตรเดิม)
//    - mode = grace    -> ผ่อนผันตามจำนวนนาทีที่ตั้งไว้ (0 = ไม่ผ่อนผัน)
//    - mode = deadline -> แปลง "เวลาเข้างานล่าสุด" เป็นจำนวนนาทีนับจากเวลาเข้ากะ
//      เพื่อให้ตรรกะเดิม (หักพักเที่ยง / กันทับซ้อนช่วงลา) ใช้ต่อได้เหมือนเดิม
//      เช่น กะเริ่ม 07:30 + เข้างานไม่เกิน 08:00 => ผ่อนผัน 30 นาที
// ============================================================
function resolveLatenessRule($rules, $dateStr) {
    $picked = null;
    foreach ($rules as $r) {
        $eff = $r['effective_date'] ?? '';
        if ($eff === '') continue;
        if ($eff <= $dateStr) { $picked = $r; } else { break; }
    }
    return $picked;
}

function resolveGraceMinutes($rules, $dateStr, $shift_start, $default) {
    $picked = resolveLatenessRule($rules, $dateStr);
    if ($picked === null) return $default;

    $mode = $picked['mode'] ?? 'grace';
    if ($mode === 'deadline') {
        if (!$shift_start) return 0;
        $h  = (float)($picked['deadline_hour'] ?? 0);
        $hh = (int)floor($h);
        $mm = (int)round(($h - $hh) * 60);
        if ($mm >= 60) { $hh += 1; $mm -= 60; }
        $deadline = clone $shift_start;
        $deadline->setTime($hh, $mm, 0);
        $diff = ($deadline->getTimestamp() - $shift_start->getTimestamp()) / 60;
        return max(0, (int)round($diff));
    }
    return max(0, (int)($picked['grace_minutes'] ?? 0));
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
    $is_today = ($d === $today->format('Y-m-d'));

    // ✅ วันอนาคต -> ข้ามเสมอ
    //    วันนี้ -> ปกติข้ามด้วย เพราะวันยังไม่จบ ยังไม่สแกนออก
    //             ถ้าคิดเลยจะกลายเป็น "ขาดงาน/ออกก่อนเวลา" ทั้งวัน
    //             แต่ถ้าผู้เรียกส่ง include_today=true (แอปมือถือ)
    //             จะคิดเฉพาะ "สายเข้างาน" ให้เห็นผลทันที (ดูบล็อก $is_today ด้านล่าง)
    if ($cursor > $today || ($is_today && !$include_today)) {
        $cursor->modify('+1 day');
        continue;
    }

    // ✅ skip วันก่อนเริ่มงาน — ยังไม่เป็นพนักงาน ไม่นับเป็นขาดงาน
    if ($start_work !== null && $cursor < $start_work) {
        $cursor->modify('+1 day');
        continue;
    }

    // ✅ skip วันหลังลาออก — ไม่นับขาดงานหลังวันลาออก (ฝั่ง Odoo จะ prorate ฐานเงินเดือนตามวันที่ทำแทน)
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

        // ✅ manual_time_log ประเภท "ถือว่ามาทำงานจริง" ที่อนุมัติแล้ว → OVERRIDE checkin_logs
        //    รวม: ลืมลงเวลา / ทำงานนอกสถานที่ / ระบบมีปัญหา
        //    ไม่รวม: ขอโอที, ทำงานวันหยุด, ค่าเบี้ยเลี้ยงออกนอกสถานที่ (เป็น OT/เบี้ยเลี้ยง = เงิน ไม่ใช่เวลาทำงาน)
        //            และรายการเงินอื่น (ค่าอาหาร/ค่ารักษา/ค่าตัวนักแสดง/ไม่ระบุ)
        //    แยกตาม reason_type ด้วย เพราะใบเตือนต้องรู้ว่า "เวลาเข้างานมาจากไหน"
        //    (ยอดหักเงินยังได้ค่าชุดเดิมเป๊ะ: MIN(checkin_time) / MAX(checkout_time))
        $checkin_scanned = ($checkin !== null);   // สแกนเข้างานเองจริง
        $checkin_excused = false;                 // ได้เวลาเข้างานจากเหตุที่ไม่ใช่ความผิดพนักงาน
        $man_ci = null;
        $man_co = null;

        $qman = $mysqli->query("SELECT reason_type, MIN(checkin_time) AS ci, MAX(checkout_time) AS co
                                FROM manual_time_logs
                                WHERE user_id='$user_id' AND work_date='$d'
                                  AND reason_type IN ('ลืมลงเวลา','ทำงานนอกสถานที่','ระบบมีปัญหา')
                                  AND state IN ({$manual_states})
                                GROUP BY reason_type");

        if ($qman) {
            while ($row = $qman->fetch_assoc()) {
                if (!empty($row['ci'])) {
                    if ($man_ci === null || $row['ci'] < $man_ci) $man_ci = $row['ci'];
                    // "ลืมลงเวลา" = พนักงานลืมกดเอง ไม่ยกเว้นให้ในใบเตือน
                    // ส่วนนอกสถานที่/ระบบมีปัญหา ไม่ใช่ความผิดพนักงาน จึงยกเว้น
                    if ($row['reason_type'] !== 'ลืมลงเวลา') $checkin_excused = true;
                }
                if (!empty($row['co'])) {
                    if ($man_co === null || $row['co'] > $man_co) $man_co = $row['co'];
                }
            }
        }
        if ($man_ci !== null) $checkin  = new DateTime("$d ".$man_ci);
        if ($man_co !== null) $checkout = new DateTime("$d ".$man_co);

        // ✅ วันนี้ (เข้ามาถึงตรงนี้ได้เฉพาะตอน include_today=true)
        //    สแกนเข้าแล้วแต่ยังไม่สแกนออก -> คิดเฉพาะ "สายเข้างาน"
        //    ไม่แตะ ขาดงาน / ออกก่อนเวลา และ **ไม่บวกเข้ายอดรวมที่ใช้คิดเงิน**
        //    ($total_lateness / $total_late_in) เพราะวันยังไม่จบ
        //    ยอดหักต้องนิ่งจนกว่าจะผ่านวันไปแล้ว
        if ($is_today) {
            if ($checkin) {
                $lateRaw = ($checkin->getTimestamp() - $shift_start->getTimestamp())/60;
                $lateMin = 0;
                if ($lateRaw > 0) {
                    $lateRaw -= getLunchOverlapMinutes($shift_start, $checkin);
                    foreach ($leave_intervals as $iv) {
                        $lateRaw -= getOverlapMinutes($shift_start, $checkin, $iv[0], $iv[1]);
                    }
                    $lateMin = max(0, (int)floor(round($lateRaw, 6)));
                }
                $is_first_workday = ($start_work !== null && $d === $start_work->format('Y-m-d'));
                $grace_today = resolveGraceMinutes($lateness_rules, $d, $shift_start, $grace_period);
                if (!$is_first_workday && $lateMin > $grace_today) {
                    $late_log[] = [
                        'date'=>$d,
                        'minutes'=>$lateMin,
                        'checkin'=>$checkin->format('H:i'),
                        'shift_start'=>$shift_start->format('H:i'),
                        'grace'=>$grace_today,
                        'today'=>true,   // วันยังไม่จบ ยังไม่รวมในยอดหัก
                    ];
                }
            }
            $cursor->modify('+1 day');
            continue;
        }

        // ✅ เกณฑ์ "ไม่ได้ลงเวลาเข้างาน" — ใช้ออกใบเตือนเท่านั้น ไม่แตะยอดหักเงิน
        //    นับเมื่อ: ไม่ได้สแกนเข้าเอง + ไม่มีเหตุยกเว้น + ไม่มีใบลา
        //    → ลืมกดเข้างาน แล้วมาขอเพิ่มเวลาทีหลัง = ยังนับ (คือสิ่งที่ใบเตือนเตือน)
        //    → เข้างานแล้ว แค่ลืมกดออกงาน = ไม่นับ
        //    → ทำงานนอกสถานที่ / ระบบมีปัญหา / มีใบลา = ไม่นับ
        if (empty($leaves) && !$checkin_scanned && !$checkin_excused) {
            $missed_no_checkin_log[] = $d;
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

            // ✅ พนักงานใหม่ "วันแรก" (วันที่กำลังคำนวณ == วันเริ่มงาน)
            //    → ข้ามการนับ "สายเข้างาน" อย่างเดียว เพราะวันแรกอาจกำลังสอนการลงเวลาเข้า
            //    (ออกก่อนเวลา / ขาดงาน / ลา ยังคิดตามปกติเหมือนเดิม)
            $is_first_workday = ($start_work !== null && $d === $start_work->format('Y-m-d'));

            // ✅ นาทีที่ผ่อนผันของ "วันนั้น" ตามสูตรที่ตั้งไว้ (ไม่มีสูตร = สูตรเดิม)
            $grace_today = resolveGraceMinutes($lateness_rules, $d, $shift_start, $grace_period);

            if (!$is_first_workday && $lateMin > $grace_today) {
                $total_lateness += $lateMin;
                $total_late_in  += $lateMin;
                $late_log[] = [
                    'date'=>$d,
                    'minutes'=>$lateMin,
                    'checkin'=>$checkin->format('H:i'),         // เวลาเข้าจริง
                    'shift_start'=>$shift_start->format('H:i'), // เวลากะเริ่ม
                    'grace'=>$grace_today,                      // นาทีที่ผ่อนผันของวันนั้น
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
        'missed_no_checkin_log'=>$missed_no_checkin_log,
        'late_checkin_log'=>$late_log,
        'early_checkout_log'=>$early_log,
        'leave_log'=>$leave_log,
        'holidays'=>$holidays
    ]
],JSON_UNESCAPED_UNICODE);

$mysqli->close();
?>
