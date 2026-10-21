odoo.define('npd_partner_rd_lookup.rd_lookup', function (require) {
    "use strict";

    var Widget = require('web.Widget');
    var widgetRegistry = require('web.widget_registry');
    var Dialog = require('web.Dialog');

    // ปุ่มใต้เลขผู้เสียภาษี: popup ค้นหาข้อมูลจากกรมสรรพากร แล้วเติมลงฟอร์ม (ไม่ต้องบันทึกผู้ติดต่อก่อน)
    var RdLookupButton = Widget.extend({
        className: 'o_npd_rd_lookup',
        events: {'click .o_npd_rd_btn': '_onOpen'},

        init: function (parent, record, node) {
            this._super.apply(this, arguments);
            this.record = record;
        },
        start: function () {
            this.$el.html('<button type="button" class="btn btn-link p-0 o_npd_rd_btn">' +
                '<i class="fa fa-search"/> ค้นหาข้อมูลจากกรมสรรพากร</button>');
            return this._super.apply(this, arguments);
        },
        updateState: function (state) {
            this.record = state;
        },

        _onOpen: function () {
            var self = this;
            var data = this.record.data || {};
            var result = null;
            var $content = $(
                '<div class="o_npd_rd_dialog">' +
                '  <div class="form-row">' +
                '    <div class="col-md-7"><label>เลขประจำตัวผู้เสียภาษี (13 หลัก)</label>' +
                '      <input type="text" class="form-control o_npd_rd_vat" maxlength="20"/></div>' +
                '    <div class="col-md-3"><label>รหัสสาขา</label>' +
                '      <input type="text" class="form-control o_npd_rd_branch" maxlength="5" placeholder="00000"/></div>' +
                '    <div class="col-md-2 d-flex align-items-end">' +
                '      <button type="button" class="btn btn-secondary btn-block o_npd_rd_search">ค้นหา</button></div>' +
                '  </div>' +
                '  <div class="text-muted small mt-1">สำนักงานใหญ่ใช้ 00000 · ข้อมูลจากระบบตรวจสอบผู้ประกอบการจดทะเบียน VAT ของกรมสรรพากร</div>' +
                '  <div class="o_npd_rd_result mt-3"/>' +
                '</div>');
            $content.find('.o_npd_rd_vat').val(data.vat || '');
            $content.find('.o_npd_rd_branch').val(data.branch || '00000');

            var dialog = new Dialog(this, {
                title: 'ค้นหาข้อมูลบริษัทจากกรมสรรพากร',
                size: 'medium',
                $content: $content,
                buttons: [
                    {text: 'ใช้ข้อมูลนี้', classes: 'btn-primary o_npd_rd_apply', click: function () {
                        if (!result || !result.ok) {
                            return;
                        }
                        self._apply(result.values);
                        dialog.close();
                    }},
                    {text: 'ปิด', close: true},
                ],
            });

            var search = function () {
                var vat = $content.find('.o_npd_rd_vat').val();
                var branch = $content.find('.o_npd_rd_branch').val();
                var $res = $content.find('.o_npd_rd_result');
                $res.html('<div class="text-muted"><i class="fa fa-spinner fa-spin"/> กำลังค้นหา...</div>');
                dialog.$footer.find('.o_npd_rd_apply').prop('disabled', true);
                return self._rpc({
                    model: 'res.partner',
                    method: 'npd_rd_lookup_values',
                    args: [vat, branch, self.record.res_id || false],
                }).then(function (res) {
                    result = res;
                    if (!res.ok) {
                        $res.html($('<div class="alert alert-warning mb-0"/>').text(res.message));
                        return;
                    }
                    var $table = $('<table class="table table-sm mb-2"/>');
                    _.each(res.display, function (row) {
                        $table.append($('<tr/>').append($('<th class="w-25"/>').text(row[0]), $('<td/>').text(row[1])));
                    });
                    $res.empty().append($table);
                    if (res.warning) {
                        $res.append($('<div class="alert alert-warning mb-0"/>').text(res.warning));
                    }
                    dialog.$footer.find('.o_npd_rd_apply').prop('disabled', false);
                });
            };
            dialog.opened().then(function () {
                dialog.$footer.find('.o_npd_rd_apply').prop('disabled', true);
                $content.find('.o_npd_rd_search').on('click', search);
                $content.find('input').on('keydown', function (ev) {
                    if (ev.which === 13) {
                        ev.preventDefault();
                        search();
                    }
                });
                $content.find('.o_npd_rd_vat').focus();
                if ($content.find('.o_npd_rd_vat').val()) {
                    search();
                }
            });
            dialog.open();
        },

        _apply: function (values) {
            var changes = {};
            var fields = this.record.fields || {};
            _.each(values, function (value, fname) {
                if (!fields[fname]) {
                    return;
                }
                if (fields[fname].type === 'many2one') {
                    changes[fname] = {id: value[0], display_name: value[1]};
                } else {
                    changes[fname] = value;
                }
            });
            this.trigger_up('field_changed', {
                dataPointID: this.record.id,
                changes: changes,
            });
        },
    });

    widgetRegistry.add('npd_rd_lookup', RdLookupButton);
    return RdLookupButton;
});
