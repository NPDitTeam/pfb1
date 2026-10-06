odoo.define('npd_partner_tax_branch.sale_order_tax_branch', function (require) {
    "use strict";

    /**
     * ใบสั่งขาย: เลือกลูกค้าที่เป็นบริษัทแต่ยังไม่มีรหัสสาขา (Tax Branch)
     * → เด้งหน้าต่างให้กรอกทันที แล้วบันทึกกลับไปที่ลูกค้า
     *
     * เสริมเข้าไปใน controller ของ js_class="sale_discount_form" (ฟอร์มใบสั่งขาย
     * มาตรฐาน) แทนการตั้ง js_class ใหม่ จะได้ไม่ทับความสามารถเดิมของ sale
     */
    const core = require('web.core');
    const SaleOrderView = require('sale.SaleOrderView');
    const _t = core._t;

    SaleOrderView.prototype.config.Controller.include({

        _confirmChange: function (id, fields) {
            const result = this._super.apply(this, arguments);
            if (this.modelName === 'sale.order' && id === this.handle
                    && fields.includes('partner_id')) {
                Promise.resolve(result).then(() => this._npdCheckTaxBranch());
            }
            return result;
        },

        async _npdCheckTaxBranch() {
            const partner = this.model.get(this.handle).data.partner_id;
            if (!partner || !partner.res_id || this._npdTaxBranchOpen) {
                return;
            }
            const missing = await this._rpc({
                model: 'res.partner',
                method: 'npd_tax_branch_missing',
                args: [partner.res_id],
            });
            if (!missing) {
                return;
            }
            this._npdTaxBranchOpen = true;
            await this.do_action('npd_partner_tax_branch.npd_tax_branch_wizard_action', {
                additional_context: {default_partner_id: partner.res_id},
                on_close: (infos) => {
                    this._npdTaxBranchOpen = false;
                    if (infos && infos.npd_tax_branch_saved) {
                        return;
                    }
                    // ปิดหน้าต่างโดยไม่กรอก: ไม่ให้ใช้ลูกค้ารายนี้ต่อจนกว่าจะมีรหัสสาขา
                    // ยิงผ่าน renderer (ลูก) เพราะ trigger_up จาก controller เอง
                    // จะวิ่งขึ้นไปหา action manager ไม่ผ่าน handler ของ controller
                    this.renderer.trigger_up('field_changed', {
                        dataPointID: this.handle,
                        changes: {partner_id: false},
                    });
                    this.displayNotification({
                        type: 'warning',
                        title: _t('ยังไม่ได้กรอกรหัสสาขา'),
                        message: _t('ต้องกรอกรหัสสาขา (Tax Branch) ของลูกค้าบริษัทก่อน จึงจะเลือกลูกค้ารายนี้ได้'),
                        sticky: false,
                    });
                },
            });
        },
    });
});
