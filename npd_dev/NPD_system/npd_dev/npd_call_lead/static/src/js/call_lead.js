odoo.define('npd_call_lead.call_action', function (require) {
    "use strict";

    var FormController = require('web.FormController');
    var rpc = require('web.rpc');
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var _t = core._t;

    FormController.include({

        _onButtonClicked: function (ev) {
            var self = this;
            var buttonName = ev.data.attrs ? ev.data.attrs.name : '';

            // ตรวจสอบว่าเป็นปุ่ม action_dial_now
            if (buttonName === 'action_dial_now') {
                ev.stopPropagation();

                var record = this.model.get(this.handle);
                var recordId = record.data.id;

                console.log('NPD Call Lead: Dial clicked, ID:', recordId);

                // เรียก RPC เพื่อบันทึกเวลาและรับ phone number
                rpc.query({
                    model: 'npd.call.lead.log',
                    method: 'js_start_call',
                    args: [[recordId]],
                }).then(function (result) {
                    console.log('NPD Call Lead: Result:', result);

                    if (result && result.success && result.phone) {
                        // สร้าง link สำหรับโทร
                        var telLink = $('<a>').attr('href', 'tel:' + result.phone).css('display', 'none');
                        $('body').append(telLink);
                        telLink[0].click();
                        telLink.remove();

                        // Reload record after 500ms
                        setTimeout(function () {
                            self.reload();
                        }, 500);

                    } else {
                        Dialog.alert(self, result ? result.error : _t('เกิดข้อผิดพลาด'));
                    }
                }).guardedCatch(function (error) {
                    console.error('NPD Call Lead: Error:', error);
                });

                return;
            }

            this._super.apply(this, arguments);
        },
    });

    console.log('NPD Call Lead: Call Action Loaded Successfully');
});
