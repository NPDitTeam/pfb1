odoo.define('bi_advance_branch_pos.pos_advance', function (require) {
    "use strict";

    var models = require('point_of_sale.models');
    
    models.load_fields('pos.session', ['address','logo','contact_address',
        'phone','vat','email','website','com_name']);

});
