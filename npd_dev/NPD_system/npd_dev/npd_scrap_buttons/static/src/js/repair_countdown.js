odoo.define('npd_scrap_buttons.repair_countdown', function (require) {
"use strict";

/**
 * Widget: npd_repair_countdown
 * ============================
 * นับถอยหลัง SLA การซ่อม 48 ชั่วโมง แบบเรียลไทม์
 *
 * ใช้ได้ 2 แบบ
 *   1) วางบนฟิลด์ datetime ที่เก็บ "เวลาครบกำหนด" โดยตรง
 *        <field name="repair_deadline" widget="npd_repair_countdown"
 *               options="{'done_field': 'repair_end_date'}"/>
 *   2) วางบนฟิลด์ char ที่เซิร์ฟเวอร์คำนวณข้อความมาให้แล้ว แล้วชี้ไปที่ฟิลด์
 *      เวลาครบกำหนดผ่าน option deadline_field (แบบนี้ถ้า JS ยังไม่ถูกโหลด
 *      ผู้ใช้จะยังเห็นข้อความที่ถูกต้อง ณ ตอนโหลดหน้า แทนที่จะเห็นค่าดิบ)
 *        <field name="repair_sla_text" widget="npd_repair_countdown"
 *               options="{'deadline_field': 'repair_deadline', ...}"/>
 *
 * เงื่อนไขการแสดงผล
 *   - มีค่าใน done_field (ซ่อมเสร็จแล้ว)
 *       * เสร็จก่อนครบกำหนด  -> "ซ่อมสำเร็จ"        (เขียว, หยุดนิ่ง)
 *       * เสร็จหลังครบกำหนด  -> "เกินกำหนด HH:MM:SS" (แดง, ค้างค่าที่เกินจริง ไม่วิ่งต่อ)
 *   - ยังไม่เสร็จ (นับถอยหลังลดทุกวินาที)
 *       * เหลือ > 24 ชม.     -> "HH:MM:SS"           (เขียว)
 *       * เหลือ <= 24 ชม.    -> "HH:MM:SS"           (เหลือง)
 *       * นับถึง 0 แล้ว      -> "เกินกำหนด HH:MM:SS" (แดง, วิ่งเพิ่มทุกวินาที)
 *
 * option warn_minutes: เกณฑ์เปลี่ยนเขียว -> เหลือง (ค่าตั้งต้น 24 ชม.)
 *
 * option count_field (ถ้ามี): จำนวนใบแจ้งซ่อมที่ยังค้างของแถวนั้น ถ้ามากกว่า 1 ใบ
 * จะต่อท้ายเป็น "(N ใบ)" เพื่อบอกว่าเวลาที่จับอยู่คือใบที่ใกล้ครบกำหนดที่สุด
 *
 * ภาระเซิร์ฟเวอร์ = 0
 *   ค่าที่ต้องใช้มีแค่ 2 ฟิลด์ที่โหลดมาพร้อมแถวอยู่แล้ว การนับเวลาทำในเบราว์เซอร์
 *   ล้วน ๆ ไม่มีการยิง RPC / ไม่มี cron ฝั่งเซิร์ฟเวอร์ และใช้ setInterval
 *   "ตัวเดียว" ร่วมกันทุก widget ในหน้า (ดู CountdownTicker) แม้รายงานจะมี
 *   หลายร้อยแถวก็ยังเป็น timer เดียว
 */

var AbstractField = require('web.AbstractField');
var fieldRegistry = require('web.field_registry');
var fieldUtils = require('web.field_utils');

var TICK_INTERVAL = 1000;
// เหลือเวลามากกว่าเท่านี้ = เขียว, น้อยกว่าหรือเท่ากับ = เหลือง (override ได้ด้วย
// option warn_minutes) หมายเหตุ: ถ้าตั้ง SLA สั้นกว่าเกณฑ์นี้เพื่อทดสอบ
// ป้ายจะเป็นเหลืองตลอดจนกว่าจะเกินกำหนด
var DEFAULT_WARN_MINUTES = 24 * 60;

// ---------------------------------------------------------------------------
// ตัวจับเวลากลาง: 1 หน้าจอ = setInterval 1 ตัว (subscriber pattern)
// ---------------------------------------------------------------------------
var CountdownTicker = {
    _widgets: [],
    _handle: null,

    subscribe: function (widget) {
        if (this._widgets.indexOf(widget) === -1) {
            this._widgets.push(widget);
        }
        if (!this._handle) {
            this._handle = window.setInterval(this._tick.bind(this), TICK_INTERVAL);
        }
    },

    unsubscribe: function (widget) {
        var index = this._widgets.indexOf(widget);
        if (index !== -1) {
            this._widgets.splice(index, 1);
        }
        if (!this._widgets.length && this._handle) {
            window.clearInterval(this._handle);
            this._handle = null;
        }
    },

    _tick: function () {
        // แท็บที่ไม่ได้เปิดอยู่ ไม่ต้องเสียแรงวาด
        if (document.hidden) {
            return;
        }
        var widgets = this._widgets.slice();
        for (var i = 0; i < widgets.length; i++) {
            widgets[i]._refresh();
        }
    },
};

// ---------------------------------------------------------------------------
// helper
// ---------------------------------------------------------------------------
function pad2(n) {
    return n < 10 ? '0' + n : '' + n;
}

/**
 * นาฬิกาจับเวลาแบบ HH:MM:SS (ชั่วโมงไม่เกิน 24 เพราะเกิน 1 วันจะขึ้นเป็น "N วัน")
 * เช่น  47 ชม. -> "1 วัน 23:00:00" , 5 ชม. -> "05:12:07"
 */
function formatClock(totalSeconds) {
    totalSeconds = Math.max(0, Math.floor(totalSeconds));
    var days = Math.floor(totalSeconds / 86400);
    var hours = Math.floor((totalSeconds % 86400) / 3600);
    var minutes = Math.floor((totalSeconds % 3600) / 60);
    var seconds = totalSeconds % 60;

    var clock = pad2(hours) + ':' + pad2(minutes) + ':' + pad2(seconds);
    return days ? days + ' วัน ' + clock : clock;
}

// ---------------------------------------------------------------------------
// widget
// ---------------------------------------------------------------------------
var RepairCountdown = AbstractField.extend({
    supportedFieldTypes: ['datetime', 'char'],
    className: 'o_npd_repair_countdown',
    events: {
        'click .o_npd_clickable': '_onClick',
    },

    init: function () {
        this._super.apply(this, arguments);
        // ถ้าไม่ได้ระบุ deadline_field แปลว่า widget วางอยู่บนฟิลด์ deadline เอง
        this.deadlineField = this.nodeOptions.deadline_field || false;
        this.doneField = 'done_field' in this.nodeOptions
            ? this.nodeOptions.done_field
            : 'repair_end_date';
        // ฟิลด์จำนวนใบแจ้งซ่อมที่ยังค้าง (ใช้เฉพาะในรายงานที่ 1 แถวรวมได้หลายใบ)
        this.countField = this.nodeOptions.count_field || false;
        this.warnSeconds = (this.nodeOptions.warn_minutes || DEFAULT_WARN_MINUTES) * 60;
        // ชื่อ method บนโมเดล ที่จะเรียกเมื่อคลิกที่ป้าย (drill-down ดูรายใบ)
        this.clickAction = this.nodeOptions.click_action || false;
    },

    start: function () {
        CountdownTicker.subscribe(this);
        return this._super.apply(this, arguments);
    },

    destroy: function () {
        CountdownTicker.unsubscribe(this);
        this._super.apply(this, arguments);
    },

    //----------------------------------------------------------------------
    // Private
    //----------------------------------------------------------------------

    /**
     * @returns {Object|null} {code, seconds, live}
     */
    /**
     * @returns {Moment|false} เวลาครบกำหนด
     */
    _getDeadline: function () {
        return this.deadlineField ? this.recordData[this.deadlineField] : this.value;
    },

    _computeState: function () {
        var deadline = this._getDeadline();
        if (!deadline) {
            return null;
        }
        var deadlineTs = deadline.valueOf();

        var done = this.doneField ? this.recordData[this.doneField] : false;
        if (done) {
            var late = Math.floor((done.valueOf() - deadlineTs) / 1000);
            return late > 0
                ? {code: 'overdue', seconds: late, live: false}
                : {code: 'repaired', seconds: 0, live: false};
        }

        var diff = Math.floor((deadlineTs - Date.now()) / 1000);
        return diff >= 0
            ? {code: 'waiting', seconds: diff, live: true}
            : {code: 'overdue', seconds: -diff, live: true};
    },

    _refresh: function () {
        if (this.isDestroyed() || !this.$el || !this.$el.length) {
            return;
        }
        var info = this._computeState();
        if (!info) {
            // ไม่มีเวลาครบกำหนด -> โชว์ค่าที่เซิร์ฟเวอร์ส่งมา (ถ้าเป็นฟิลด์ char)
            this.$el.text(this.deadlineField && this.value ? this.value : '');
            return;
        }

        var text;
        var cssClass;
        if (info.code === 'repaired') {
            text = 'ซ่อมสำเร็จ';
            cssClass = 'badge badge-success';
        } else if (info.code === 'overdue') {
            text = 'เกินกำหนด ' + formatClock(info.seconds);
            cssClass = 'badge badge-danger';
        } else {
            // นับถอยหลังเฉย ๆ พอถึง 00:00:00 จะพลิกไปเป็น "เกินกำหนด" เอง
            // เหลือเยอะ = เขียว, เข้าเขตใกล้ครบกำหนด = เหลือง
            text = formatClock(info.seconds);
            cssClass = info.seconds > this.warnSeconds
                ? 'badge badge-success'
                : 'badge badge-warning';
        }

        var count = this.countField ? this.recordData[this.countField] : 0;
        if (count > 1) {
            text += ' (' + count + ' ใบ)';
        }

        var title = 'ครบกำหนด: ' + fieldUtils.format.datetime(
            this._getDeadline(), {type: 'datetime'}, {});
        if (count > 1) {
            title += '\nมีใบแจ้งซ่อมค้างอยู่ ' + count + ' ใบ — เวลาที่แสดงคือใบที่ใกล้ครบกำหนดที่สุด';
        }
        var style = 'white-space: nowrap;';
        if (this.clickAction) {
            cssClass += ' o_npd_clickable';
            style += ' cursor: pointer; text-decoration: underline;';
            title += '\nคลิกเพื่อดูใบแจ้งซ่อมรายใบ';
        }
        var $badge = $('<span/>', {
            'class': cssClass,
            text: text,
            title: title,
            style: style,
        });
        this.$el.empty().append($badge);
    },

    /**
     * คลิกที่ป้าย -> เรียก method บนโมเดล (คืนค่าเป็น act_window) เหมือนกดปุ่ม
     * type="object" ในแถว list โดยยืมกลไก button_clicked ของ renderer
     */
    _onClick: function (ev) {
        if (!this.clickAction || !this.record) {
            return;
        }
        ev.stopPropagation();
        this.trigger_up('button_clicked', {
            attrs: {name: this.clickAction, type: 'object'},
            record: this.record,
        });
    },

    _render: function () {
        this._refresh();
    },
});

fieldRegistry.add('npd_repair_countdown', RepairCountdown);

return {
    RepairCountdown: RepairCountdown,
    CountdownTicker: CountdownTicker,
};

});
