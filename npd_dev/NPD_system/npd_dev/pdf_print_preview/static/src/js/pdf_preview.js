odoo.define("pdf_print_preview.report", function (require) {
    "use strict";

    var ActionManager = require("web.ActionManager");
    var framework = require("web.framework");
    var session = require("web.session");
    var core = require('web.core');

    var _t = core._t;
    var _lt = core._lt;

    // Messages that will be shown to the user (if needed).
    var WKHTMLTOPDF_MESSAGES = {
        "install": _lt("Unable to find Wkhtmltopdf on this \nsystem. The report will be shown in html.<br><br><a href='http://wkhtmltopdf.org/' target='_blank'>\nwkhtmltopdf.org</a>"),
        "workers": _lt("You need to start OpenERP with at least two \nworkers to print a pdf version of the reports."),
        "upgrade": _lt("You should upgrade your version of\nWkhtmltopdf to at least 0.12.0 in order to get a correct display of headers and footers as well as\nsupport for table-breaking between pages.<br><br><a href='http://wkhtmltopdf.org/' \ntarget='_blank'>wkhtmltopdf.org</a>"),
        "broken": _lt("Your installation of Wkhtmltopdf seems to be broken. The report will be shown in html.<br><br><a href='http://wkhtmltopdf.org/' target='_blank'>wkhtmltopdf.org</a>")
    };

    var PreviewDialog = require("pdf_print_preview.PreviewDialog");

    var wkhtmltopdf_state;

    ActionManager.include({
        _executeReportAction: function (action, options) {
            var self = this;

            action = _.clone(action);

            var url = "/report/pdf/" + action.report_name;
            var filename = action.report_name;
            var title = action.name;
            var pdfFileName = action.name;
            var newUrl = false;

            if( pdfFileName !== undefined )
                pdfFileName = "?" + pdfFileName.replace(/[/?%#&=]/g, "") + ".pdf";

            if (_.isUndefined(action.data) || _.isNull(action.data) || (_.isObject(action.data) && _.isEmpty(action.data))) {
                url += "/" + action.context.active_ids.join(",");
                newUrl = url + pdfFileName;
            }

            else {
                var serializedOptionsPath = 'options=' + encodeURIComponent(JSON.stringify(action.data));
                serializedOptionsPath += '&context=' + encodeURIComponent(JSON.stringify(action.context));
                newUrl = url;
                url += "?" + serializedOptionsPath;
                newUrl += pdfFileName + "&" + serializedOptionsPath;
            }

            if (action.report_type === "qweb-pdf") {
                framework.blockUI();
                (wkhtmltopdf_state = wkhtmltopdf_state || session.rpc("/report/check_wkhtmltopdf")).then(function (state) {
                    if (WKHTMLTOPDF_MESSAGES[state]) {
                        self.do_notify( _t("Report"), WKHTMLTOPDF_MESSAGES[state], true);
                        return $.Deferred().reject();
                    }

                    else {

                        if(session.preview_print){
                            PreviewDialog.createPreviewDialog(self, newUrl,  title);
                        }

                        if (session.automatic_printing) {
                   
                            try {
                                var pdf = window.open(url);
                                pdf.print();

                            }
                            catch(err) {
                               self.do_notify( _t("Report"), _t( "Please allow <b style='color: red;'>pop up</b> in your browser to <b>preview report</> in another tab." ), true);
                            }
                        }

                        if (!session.automatic_printing && !session.preview_print) {
                            return self._super(action, options);
                        }
                    }
                });

            framework.unblockUI();

            }else if(action.report_type != "qweb-pdf"){
                self._super(action, options);
            }

            return Promise.reject();
        }
    });

});
