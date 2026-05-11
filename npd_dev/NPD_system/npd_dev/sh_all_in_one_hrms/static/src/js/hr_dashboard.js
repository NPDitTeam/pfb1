odoo.define('sh_hr_dashboard.dashboard', function (require) {
    "use strict";
    var AbstractAction = require('web.AbstractAction');
    var ajax = require('web.ajax');
    var core = require('web.core');
    var _t = core._t;
    var rpc = require('web.rpc');
    var session = require('web.session');
    var QWeb = core.qweb;
    var HRDashboardView = AbstractAction.extend({

        events: {

            'click .create_attendance': 'action_create_attendance',
            'click .create_leave': 'action_create_leave',
            'click .create_expense': 'action_create_expense',
            'click .open_employee_leave': 'open_employee_leave',
            'click .open_employee_attendnace': 'open_employee_attendnace',
            'click .open_employee_expense': 'open_employee_expense',
            'click .open_employee_contract': 'open_employee_contract',
            'click .open_cmp_policy': 'open_cmp_policy',


        },


        open_cmp_policy: function (event) {
            var self = this;
            event.stopPropagation();
            event.preventDefault();

            const currentCompanyId = session.user_context.allowed_company_ids[0];

            if (currentCompanyId) {

                self.do_action({
                    name: _t("Company Policy"),
                    type: 'ir.actions.act_window',
                    res_model: 'sh.company.policy.wizard',
                    view_mode: 'form',
                    views: [[false, 'form']],
                    context: {
                        'default_company_id': currentCompanyId,
                    },
                    target: 'new'
                });
            }
        },

        open_employee_contract: function (event) {
            var self = this;
            event.stopPropagation();
            event.preventDefault();

            $.get("/get_user_name", function (data) {
                data = JSON.parse(data);
                if (data['employee']) {
                    self.do_action({
                        name: _t("Contract"),
                        type: 'ir.actions.act_window',
                        res_model: 'hr.contract',
                        view_mode: 'tree,kanban,form',
                        views: [
                            [false, 'tree'],
                            [false, 'kanban'],
                            [false, 'form'],
                        ],
                        domain: [['employee_id', '=', data['employee']]],
                        target: 'current'
                    });
                }

            });

        },

        open_employee_expense: function (event) {
            var self = this;
            event.stopPropagation();
            event.preventDefault();

            $.get("/get_user_name", function (data) {
                data = JSON.parse(data);
                if (data['employee']) {
                    self.do_action({
                        name: _t("Expense"),
                        type: 'ir.actions.act_window',
                        res_model: 'hr.expense',
                        view_mode: 'tree,kanban,form,graph,pivot,activity',
                        views: [
                            [false, 'tree'],
                            [false, 'kanban'],
                            [false, 'form'],
                            [false, 'graph'],
                            [false, 'pivot'],
                            [false, 'activity']
                        ],
                        domain: [['employee_id', '=', data['employee']]],
                        target: 'current'
                    });
                }

            });

        },
        open_employee_attendnace: function (event) {
            var self = this;
            event.stopPropagation();
            event.preventDefault();

            $.get("/get_user_name", function (data) {
                data = JSON.parse(data);
                if (data['employee']) {
                    self.do_action({
                        name: _t("Attendance"),
                        type: 'ir.actions.act_window',
                        res_model: 'hr.attendance',
                        view_mode: 'tree,kanban,form',
                        views: [
                            [false, 'tree'],
                            [false, 'kanban'],
                            [false, 'form']
                        ],
                        domain: [['employee_id', '=', data['employee']]],
                        target: 'current'
                    });
                }

            });

        },
        open_employee_leave: function (event) {
            var self = this;
            event.stopPropagation();
            event.preventDefault();

            $.get("/get_user_name", function (data) {
                data = JSON.parse(data);
                if (data['employee']) {
                    self.do_action({
                        name: _t("Leaves"),
                        type: 'ir.actions.act_window',
                        res_model: 'hr.leave',
                        view_mode: 'calendar,tree,form,activity',
                        views: [
                            [false, 'calendar'],
                            [false, 'tree'],
                            [false, 'form'],
                            [false, 'activity']
                        ],
                        domain: [['employee_id', '=', data['employee']]],
                        target: 'current'
                    });
                }

            });

        },
        action_create_leave: function (event) {
            var self = this;
            event.stopPropagation();
            event.preventDefault();

            $.get("/get_user_name", function (data) {
                data = JSON.parse(data);
                if (data['employee']) {
                    self.do_action({
                        name: _t("Leave Request"),
                        type: 'ir.actions.act_window',
                        res_model: 'hr.leave',
                        view_mode: 'form',
                        views: [
                            [false, 'form']
                        ],
                        context: { 'default_employee_id': data['employee'] },
                        target: 'current'
                    });
                }

            });

        },
        action_create_expense: function (event) {
            var self = this;
            event.stopPropagation();
            event.preventDefault();

            $.get("/get_user_name", function (data) {
                data = JSON.parse(data);
                if (data['employee']) {
                    self.do_action({
                        name: _t("Expense"),
                        type: 'ir.actions.act_window',
                        res_model: 'hr.expense',
                        view_mode: 'form',
                        views: [
                            [false, 'form']
                        ],
                        context: { 'default_employee_id': data['employee'] },
                        target: 'current'
                    });
                }

            });

        },
        action_create_attendance: function (event) {
            var self = this;
            event.stopPropagation();
            event.preventDefault();

            $.get("/get_user_name", function (data) {
                data = JSON.parse(data);
                if (data['attendance']) {
                    self.do_action({
                        name: _t("Attendance"),
                        type: 'ir.actions.act_window',
                        res_model: 'hr.attendance',
                        view_mode: 'form',
                        views: [
                            [false, 'form']
                        ],
                        res_id: data['attendance'],
                        target: 'current'
                    });
                } else if (data['employee']) {
                    self.do_action({
                        name: _t("Attendance"),
                        type: 'ir.actions.act_window',
                        res_model: 'hr.attendance',
                        view_mode: 'form',
                        views: [
                            [false, 'form']
                        ],
                        context: { 'default_employee_id': data['employee'] },
                        target: 'current'
                    });
                }

            });

        },
        init: function (parent, context) {
            this._super(parent, context);
            var self = this;
            $.get("/get_employee_birhday_data", function (data) {
                $("#js_id_sh_birthday_data_tbl_div").replaceWith(data);
            });

            $.get("/get_employee_anniversary_data", function (data) {
                $("#js_id_sh_anniversary_data_tbl_div").replaceWith(data);
            });

            $.get("/get_annoucement_data", function (data) {
                $("#js_id_sh_annoucement_data_tbl_div").replaceWith(data);
            });

            $.get("/get_employee_expense_data", function (data) {
                $("#js_id_sh_expense_data_tbl_div").replaceWith(data);
            });

            $.get("/get_employee_attendance_data", function (data) {
                $("#js_id_sh_attendance_data_tbl_div").replaceWith(data);
            });

            $.get("/get_employee_leave_data", function (data) {
                $("#js_id_sh_leave_data_tbl_div").replaceWith(data);
            });

            this.login_employee = [];

        },
        start: function () {
            var self = this;
            self.render();
            return this._super();
        },
        render: function () {
            var self = this;
            var hr_dashboard = QWeb.render('hr_dashboard.dashboard', {
                widget: self,
            });
            $(hr_dashboard).prependTo(self.$el);
            $.get("/get_user_name", function (data) {
                data = JSON.parse(data);
                if (data['user']) {
                    self.$el.find('.user_name').html(data['user']);
                }
                if (data['leave_count']) {
                    self.$el.find('.leave_count').html(data['leave_count']);
                }
                if (data['allocated_leave_count']) {
                    self.$el.find('.allocated_leave_count').html(data['allocated_leave_count']);
                }
                if (data['attendance_count']) {
                    self.$el.find('.attendance_count').html(data['attendance_count']);
                }
                if (data['expense_count']) {
                    self.$el.find('.expense_count').html(data['expense_count']);
                }
                if (data['contract_count']) {
                    self.$el.find('.contract_count').html(data['contract_count']);
                }

            });



            return hr_dashboard
        },

    });

    core.action_registry.add('hr_dashboard.dashboard', HRDashboardView);
    return HRDashboardView;

});

