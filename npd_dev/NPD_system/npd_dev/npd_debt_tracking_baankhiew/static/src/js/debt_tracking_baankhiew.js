odoo.define('npd_debt_tracking_baankhiew.call_action', function (require) {
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
            
            // ตรวจสอบว่าเป็นปุ่ม action_dial_now สำหรับ baankhiew
            if (buttonName === 'action_dial_now' && this.modelName === 'npd.debt.tracking.baankhiew.call.log') {
                ev.stopPropagation();
                
                var record = this.model.get(this.handle);
                var recordId = record.data.id;
                
                console.log('NPD Baankhiew: Dial clicked, ID:', recordId);
                
                // เรียก RPC เพื่อบันทึกเวลาและรับ phone number
                rpc.query({
                    model: 'npd.debt.tracking.baankhiew.call.log',
                    method: 'js_start_call',
                    args: [[recordId]],
                }).then(function (result) {
                    console.log('NPD Baankhiew: Result:', result);
                    
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
                    console.error('NPD Baankhiew: Error:', error);
                    
                    // ตรวจสอบว่าเป็น MissingError หรือไม่
                    var errorMsg = _t('เกิดข้อผิดพลาดในการโทร');
                    if (error && error.message) {
                        var msg = error.message;
                        if (msg.data && msg.data.message) {
                            errorMsg = msg.data.message;
                        } else if (msg.data && msg.data.name === 'odoo.exceptions.MissingError') {
                            errorMsg = _t('รายการศูนย์หายหรือถูกลบไปแล้ว\n\nกรุณาปิดหน้าต่างนี้และกดปุ่มโทรใหม่อีกครั้ง');
                        }
                    }
                    
                    Dialog.alert(self, errorMsg, {
                        title: _t('ไม่สามารถโทรได้'),
                        $content: $('<div>').html(errorMsg.replace(/\n/g, '<br/>')),
                        confirm_callback: function () {
                            // ปิด popup และ reload หน้าหลัก
                            self.do_action({'type': 'ir.actions.act_window_close'});
                        }
                    });
                });
                
                return;
            }
            
            this._super.apply(this, arguments);
        },
    });

    console.log('NPD Baankhiew: Call Action Loaded Successfully');
});
