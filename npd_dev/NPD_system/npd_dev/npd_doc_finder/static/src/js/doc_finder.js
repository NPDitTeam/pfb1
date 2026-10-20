odoo.define('npd_doc_finder.widget', function (require) {
    "use strict";

    var relational = require('web.relational_fields');
    var registry = require('web.field_registry');
    var session = require('web.session');
    var utils = require('web.utils');

    // ช่องค้นหาเลขเอกสาร: แสดงรายการมากขึ้น ไม่มีปุ่มสร้าง และเลือกแล้วเปิดเอกสารทันที
    var DocFinderMany2One = relational.FieldMany2One.extend({
        init: function () {
            this._super.apply(this, arguments);
            this.limit = 15;
            this.can_create = false;
            this.nodeOptions.no_create = true;
            this.nodeOptions.no_quick_create = true;
            this.nodeOptions.no_create_edit = true;
            this.nodeOptions.limit = 15;
            this.noOpen = true;
        },
        reinitialize: function (value) {
            var res = this._super.apply(this, arguments);
            if (value && value.id) {
                this._openDocument(value.id);
            }
            return res;
        },
        _openDocument: function (id) {
            var self = this;
            return this._rpc({
                model: 'npd.doc.finder.line',
                method: 'action_open',
                args: [[id]],
            }).then(function (action) {
                var companyId = action.npd_company_id;
                delete action.npd_company_id;
                var allowed = session.user_context.allowed_company_ids || [];
                if (companyId && allowed.indexOf(companyId) === -1) {
                    // เอกสารอยู่บริษัทที่ยังไม่ได้ติ๊กใช้งาน: เพิ่มบริษัทนั้นแล้วโหลดหน้าเอกสารใหม่
                    var cids = allowed.concat([companyId]).join(',');
                    var state = {cids: cids, model: action.res_model, id: action.res_id, view_type: 'form'};
                    if (action.id) {
                        state.action = action.id;
                    }
                    utils.set_cookie('cids', cids);
                    window.location.hash = $.param(state);
                    window.location.reload();
                    return;
                }
                return self.do_action(action);
            });
        },
    });

    registry.add('npd_doc_finder', DocFinderMany2One);
    return DocFinderMany2One;
});
