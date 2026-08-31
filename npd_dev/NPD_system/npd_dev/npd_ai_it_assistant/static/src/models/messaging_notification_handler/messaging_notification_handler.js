odoo.define('npd_ai_it_assistant/static/src/models/messaging_notification_handler/messaging_notification_handler.js', function (require) {
'use strict';

/**
 * มีเสียงเตือนทุกครั้งที่ "ตัวช่วย AI-IT" ตอบกลับ
 *
 * ของเดิม Odoo จะส่งเสียงเฉพาะตอนที่หน้าต่างไม่ได้โฟกัส
 * (_notifyNewChannelMessageWhileOutOfFocus) แต่งานนี้พนักงานนั่งจ้องแชทรออยู่
 * และบางขั้นตอน (ตัดสต๊อก/ยกเลิกเอกสาร) ใช้เวลาหลายวินาที จึงควรมีเสียงบอก
 * ว่าคำตอบมาแล้ว ไม่ต้องเฝ้าหน้าจอ
 *
 * ส่งเสียงเฉพาะข้อความของบอทตัวนี้เท่านั้น แชทกับคนอื่นยังเงียบตามค่ามาตรฐาน
 */

const { registerInstancePatchModel } = require('mail/static/src/model/model_core.js');

const session = require('web.session');

// สร้าง Audio ครั้งเดียวแล้วใช้ซ้ำ (สร้างใหม่ทุกครั้งจะกินหน่วยความจำเปล่า ๆ)
let audio;

let hasWarnedMissingBotId = false;

function warnMissingBotIdOnce() {
    if (hasWarnedMissingBotId) {
        return;
    }
    hasWarnedMissingBotId = true;
    console.warn(
        'npd_ai_it_assistant: ไม่พบ npd_ai_it_bot_partner_id ใน session ' +
        'จึงไม่รู้ว่าข้อความไหนเป็นของบอท เสียงแจ้งเตือนและไฟสถานะ AI จะไม่ทำงาน — ' +
        'สาเหตุที่พบบ่อยคือเพิ่มไฟล์ .py ใหม่แล้วสั่งแค่ -u ' +
        'ต้อง restart service ของ Odoo ด้วย'
    );
}

function playTing() {
    if (typeof Audio === 'undefined') {
        return;
    }
    if (!audio) {
        audio = new Audio();
        const ext = audio.canPlayType('audio/ogg; codecs=vorbis') ? '.ogg' : '.mp3';
        // ใช้ไฟล์เสียงเดียวกับการแจ้งเตือนแชทของ Odoo จะได้ไม่ขัดหูผู้ใช้
        audio.src = session.url('/mail/static/src/audio/ting' + ext);
    }
    // เบราว์เซอร์อาจบล็อกถ้าผู้ใช้ยังไม่เคยคลิกอะไรในหน้า — กลืน error ทิ้ง
    Promise.resolve(audio.play()).catch(() => {});
}

registerInstancePatchModel(
    'mail.messaging_notification_handler',
    'npd_ai_it_assistant/static/src/models/messaging_notification_handler/messaging_notification_handler.js',
    {
        /**
         * @override
         */
        async _handleNotificationChannelMessage(channelId, messageData) {
            const result = await this._super(channelId, messageData);
            try {
                const botPartnerId = this.env.session.npd_ai_it_bot_partner_id;
                if (!botPartnerId) {
                    // ไม่มีค่านี้ = ir.http.session_info ของโมดูลยังไม่ถูกโหลด
                    // (ไฟล์ .py ที่เพิ่มใหม่ต้อง "restart service" ไม่ใช่แค่ -u)
                    warnMissingBotIdOnce();
                    return result;
                }
                const authorId = messageData && messageData.author_id
                    ? messageData.author_id[0]
                    : false;
                if (authorId === botPartnerId) {
                    playTing();
                }
            } catch (error) {
                // เสียงเตือนพังไม่ควรทำให้ข้อความไม่ขึ้น
                console.warn('npd_ai_it_assistant: เล่นเสียงแจ้งเตือนไม่สำเร็จ', error);
            }
            return result;
        },
    }
);

});
