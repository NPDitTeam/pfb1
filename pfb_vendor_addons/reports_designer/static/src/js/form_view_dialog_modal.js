odoo.define('reports_designer.FormViewDialogModal', function(require) {
	"use strict";

var FormViewDialog = require('web.view_dialogs').FormViewDialog;
FormViewDialog.include({
	init: function(parent, options) {
		if (options.res_model == "reports.designer.section") {
			options.disable_multiple_selection =  true;			
		};
		this._super(parent, options);
		if (options.res_model == "reports.designer.fields") {
			this.dialogClass += ' modal-body_reports_designer';
		};
	},
});
});
