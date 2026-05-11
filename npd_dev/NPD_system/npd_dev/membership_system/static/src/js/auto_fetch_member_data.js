odoo.define('membership_system.auto_fetch_member_data', function (require) {
    "use strict";

    var ListController = require('web.ListController');

    ListController.include({
        willStart: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                if (self.modelName === 'membership.member') {
                    console.log('Calling action_fetch_member_data...');
                    return self._rpc({
                        model: 'membership.member',
                        method: 'action_fetch_member_data',
                    }).then(function (result) {
                        console.log('Member data updated from API.');
                    });
                }
            });
        },
    });
});
