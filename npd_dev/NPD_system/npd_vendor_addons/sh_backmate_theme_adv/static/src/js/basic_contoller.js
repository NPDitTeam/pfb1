odoo.define('sh_backmate_theme_adv.ListController', function (require) {
    "use strict";

    var ListController = require('web.ListController');

    ListController.include({
        events: _.extend({}, ListController.prototype.events, {
            'click .sh_refresh': '_onClickRefreshView',
        }),
        _onClickRefreshView:function (ev) {
           console.log("Refresh")
           this.reload()
        }
    });
});
odoo.define('sh_backmate_theme_adv.BasicController', function (require) {
    "use strict";

    var BasicController = require('web.BasicController');

    BasicController.include({
        events: _.extend({}, BasicController.prototype.events, {
            'click .sh_refresh': '_onClickRefreshView',
        }),
        _onClickRefreshView:function (ev) {
           console.log("Refresh")
           this.reload()
        }
    });
});