odoo.define('product_stock_check.barcode_auto_enter', function (require) {
    "use strict";

    var publicWidget = require('web.public.widget');

    publicWidget.registry.BarcodeAutoEnter = publicWidget.Widget.extend({
        selector: 'input[name="barcode"]',
        events: {
            'input': '_onBarcodeScanned',
        },

        _onBarcodeScanned: function (ev) {
            var self = this;
            clearTimeout(this.timeout);
            this.timeout = setTimeout(function () {
                console.log("Barcode scanned: ", self.$el.val());  // Debug log
                self.$el.trigger('change');  // Trigger onchange event after scan
            }, 200);  // ปรับ Delay ให้สั้นลงเพื่อให้ยิงแล้วทำงานเร็วขึ้น
        }
    });

    return publicWidget.registry.BarcodeAutoEnter;
});
