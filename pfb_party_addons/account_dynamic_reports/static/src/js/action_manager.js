odoo.define('account_dynamic_reports.action_manager', function (require) {
"use strict";
/**
 * The purpose of this file is to add the actions of type
 * 'xlsx' to the ActionManager.
 */

var ActionManager = require('web.ActionManager');
var framework = require('web.framework');
var session = require('web.session');


ActionManager.include({

    /**
     * Executes actions of type 'ir.actions.report'.
     *
     * @private
     * @param {Object} action the description of the action to execute
     * @param {Object} options @see doAction for details
     * @returns {Promise} resolved when the action has been executed
     */
    _executexlsxReportDownloadAction: function (action) {
        framework.blockUI();
        var def = $.Deferred();
        session.get_file({
            url: '/xlsx_reports',
            data: action.data,
            success: def.resolve.bind(def),
            complete: framework.unblockUI,
        });
        return def;
    },
    /**
     * Overrides to handle the 'ir.actions.report' actions.
     *
     * @override
     * @private
     */
    _executeReportAction: function (action, options) {
         console.log(action);
         if (action.report_type === 'xlsx'
            && action.report_name != 'l10n_th_tax_report.report_tax_report_xlsx'
            && action.report_name != 'withholding.tax.report.xlsx'
            && action.report_name != 'asset_register_xlsx'
            && action.report_name != 'mis_builder.mis_report_instance_xlsx'
            && action.report_name != 'stock_card_report.report_stock_card_report_xlsx'
         ) {
//            console.log("if >>>>>>>>> 1")
            return this._executexlsxReportDownloadAction(action, options);
//            print for gl
        }
        else {
//        console.log("if >>>>>>>> 2");
        return this._super.apply(this, arguments);
        }
        //print for thai tax report
    },
});

});