odoo.define('sale_barcode.sale_order', function (require) {
    "use strict";

    var FormController = require('web.FormController');
    var rpc = require('web.rpc');

    console.log("sale_barcode.js loaded!");

    FormController.include({
        events: {
            'keypress input[name="barcode"]': '_onBarcodeEnter',
        },

        _onBarcodeEnter: function (e) {
            if (e.key === 'Enter') {
                console.log("Enter pressed in barcode!");
                e.preventDefault();
                var self = this;
                var record = this.model.get(this.handle);
                var record_id = record.res_id;
                var $barcodeInput = $(e.target);
                var barcode_value = $barcodeInput.val();

                if (!record_id) {
                    console.log("No record ID");
                    alert("Please save the sale order first.");
                    return;
                }

                this.model.localData[this.handle].data.barcode = barcode_value;

                rpc.query({
                    model: 'sale.order',
                    method: 'action_process_barcode',
                    args: [[record_id]],
                }).then(function (result) {
                    console.log("RPC result:", result);
                    if (result && result.warning) {
                        alert(result.warning.message);
                    } else {
                        self.reload();
                        $barcodeInput.val('');
                    }
                }).fail(function (error) {
                    console.error("RPC error:", error);
                    alert("An error occurred: " + error.message);
                });
            }
        },
    });
});