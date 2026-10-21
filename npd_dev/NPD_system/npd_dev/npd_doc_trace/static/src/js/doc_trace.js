odoo.define('npd_doc_trace.widget', function (require) {
    "use strict";

    var registry = require('web.field_registry');
    var DocFinderMany2One = require('npd_doc_finder.widget');

    // เลือกเลขเอกสารแล้วให้เซิร์ฟเวอร์สร้างผลตรวจ แล้วเปิด popup ผล (แทนการเปิดหน้าเอกสาร)
    var DocTraceMany2One = DocFinderMany2One.extend({
        _openDocument: function (id) {
            var self = this;
            return this._rpc({
                model: 'npd.doc.trace.wizard',
                method: 'action_start',
                args: [id],
            }).then(function (action) {
                return self.do_action(action);
            });
        },
    });

    registry.add('npd_doc_trace', DocTraceMany2One);
    return DocTraceMany2One;
});
