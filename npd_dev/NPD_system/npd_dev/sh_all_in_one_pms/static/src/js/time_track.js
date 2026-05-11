odoo.define("sh_all_in_one_pms.time_track", function (require) {
    "use strict";
    var AbstractField = require("web.AbstractField");
    var core = require("web.core");
    var field_registry = require("web.field_registry");
    var time = require("web.time");
    var Widget = require("web.Widget");
    var _t = core._t;
    var TimeCounter = AbstractField.extend({
        supportedFieldTypes: [],

        willStart: function () {
            var self = this;
            var def = this._rpc({
                model: "account.analytic.line",
                method: "search_read",
                domain: [
                    ["task_id", "=", this.record.data.id],
                    ["end_date", "=", false],
                    ["start_date", "!=", false],
                    //  ['employee_id.user_id', '=', this.getSession().uid],
                ],
            }).then(function (result) {
                if (self.mode === "readonly") {
                    var currentDate = new Date();
                    self.duration = 0;
                    _.each(result, function (data) {
                        self.duration += data.end_date ? self._getDateDifference(data.start_date, data.end_date) : self._getDateDifference(time.auto_str_to_date(data.start_date), currentDate);
                    });
                }
            });
            return $.when(this._super.apply(this, arguments), def);
        },

        destroy: function () {
            this._super.apply(this, arguments);
            clearTimeout(this.timer);
        },

        isSet: function () {
            return true;
        },

        _getDateDifference: function (dateStart, dateEnd) {
            return moment(dateEnd).diff(moment(dateStart));
        },

        _render: function () {
            console.log("render");
            this._startTimeCounter();
        },

        _startTimeCounter: function () {
            console.log("_startTimeCounter");
            var self = this;
            this.timer = "";
            clearTimeout(this.timer);
            if (this.record.data.is_user_working) {
                this.timer = setTimeout(function () {
                    self.duration += 1000;
                    self._startTimeCounter();
                }, 1000);
            } else {
                clearTimeout(this.timer);
            }
            this.$el.html($("<span>" + moment.utc(this.duration).format("HH:mm:ss") + "</span>"));
        },
    });

    field_registry.add("task_time_counter", TimeCounter);
});

odoo.define("sh_all_in_one_pms.TaskTimerTemplate", function (require) {
    var core = require("web.core");
    var Dialog = require("web.Dialog");
    var Widget = require("web.Widget");
    var rpc = require("web.rpc");
    var SystrayMenu = require("web.SystrayMenu");

    var _t = core._t;
    var QWeb = core.qweb;

    var TimerMenu = Widget.extend({
        template: "TaskTimerTemplate",
        events: {
            "click #timer_start": "_start_timer",
            "click #timer_stop": "_stop_timer",
        },
        init: function () {
            this._super.apply(this, arguments);
            var self = this;
            this._rpc({
                model: "res.users",
                method: "search_read",
                fields: ["task_id"],
                domain: [["id", "=", this.getSession().uid]],
            }).then(function (data) {
                if (data) {
                    _.each(data, function (user) {
                        if (user.task_id) {
                            self.$("#timer_start").css("display", "none");
                            self.$("#timer_stop").css("display", "block");
                            self.$("#user_task").text(user.task_id[1]);
                            self._rpc({
                                model: "project.task",
                                method: "get_duration",
                                args: [user.task_id[0]],
                            }).then(function (duration) {
                            	
                            	let count = duration;
                            	let rAF_ID;

                            	var rAFCallback = function(callback) {
                            	  let count = callback;

                            	  let ms = Math.floor(count % 1000);
                            	  let s = Math.floor((count /  1000)) % 60;
                            	  let m = Math.floor((count / 60000)) % 60;

                            	  let h = Math.floor((count / 3600000)) % 60;
                            	  $('#task_timer').text(h + ":" + m + ":" + s);
                            	  rAF_ID = requestAnimationFrame( rAFCallback );
                            	}

                            	rAF_ID = requestAnimationFrame( rAFCallback );  
                                self._startTimeCounter(duration);
                            });
                        } else {
                            self.$("#timer_stop").css("display", "none");
                            self.$("#task_timer").css("display", "none");
                            self.$("#timer_start").css("display", "block");
                            self.$("#user_task").parent("li").css("display", "none");
                        }
                    });
                }
            });
        },
        _startTimeCounter: function (duration) {

        	let count = duration;
        	let rAF_ID;
        	var rAFCallback = function(callback) {
        	  let count = duration + callback;
        	  let ms = Math.floor(count % 1000);
        	  let s = Math.floor((count /  1000)) % 60;
        	  let m = Math.floor((count / 60000)) % 60;
        	  let h = Math.floor((count / 3600000)) % 60;
        	  $('#task_timer').text(h + ":" + m + ":" + s);
        	  rAF_ID = requestAnimationFrame( rAFCallback );
        	}
        	rAF_ID = requestAnimationFrame( rAFCallback );  

        },
        _start_timer: function (e) {
            e.preventDefault();
            this.do_action({
                type: "ir.actions.act_window",
                view_type: "form",
                view_mode: "form",
                views: [[false, "form"]],
                res_model: "sh.start.timesheet",
                target: "new",
                context: {
                    form_view_ref: "sh_task_track.start_timesheet_form",
                },
            });
        },
        _stop_timer: function (e) {
            e.preventDefault();
            var self = this;

            this._rpc({
                model: "res.users",
                method: "search_read",
                fields: ["task_id"],
                domain: [["id", "=", this.getSession().uid]],
            }).then(function (data) {
                if (data) {
                    _.each(data, function (user) {
                        if (user.task_id) {
                            self._rpc({
                                model: "project.task",
                                method: "search_read",
                                fields: ["start_time", "end_time", "total_time"],
                                domain: [["id", "=", user.task_id[0]]],
                            }).then(function (task) {
                                self.do_action({
                                    type: "ir.actions.act_window",
                                    view_type: "form",
                                    view_mode: "form",
                                    views: [[false, "form"]],
                                    res_model: "task.time.account.line",
                                    target: "new",
                                    context: {
                                        default_start_date: task[0]["start_time"],
                                        active_id: user.task_id[0],
                                        active_model: "project.task",
                                    },
                                });
                            });
                        }
                    });
                }
            });
        },
    });
    TimerMenu.prototype.sequence = 3;
    SystrayMenu.Items.push(TimerMenu);

    //return quick_menu;
    return {
        TimerMenu: TimerMenu,
    };
});