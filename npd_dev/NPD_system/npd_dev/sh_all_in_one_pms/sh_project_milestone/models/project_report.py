# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields


class ReportProjectTaskUser(models.Model):
    _inherit = "report.project.task.user"

    milestone_id = fields.Many2one("project.milestone", "Milestone")

    def _select(self):
        select_str = """
             SELECT
                    (select 1 ) AS nbr,
                    t.id as id,
                    t.date_assign as date_start,
                    t.date_end as date_end,
                    t.date_last_stage_update as date_last_stage_update,
                    t.date_deadline as date_deadline,
                    t.user_id,
                    t.project_id,
                    t.milestone_id,
                    t.priority,
                    t.name as name,
                    t.company_id,
                    t.partner_id,
                    t.stage_id as stage_id,
                    t.kanban_state as state,
                    t.working_days_close as working_days_close,
                    t.working_days_open  as working_days_open,
                    (extract('epoch' from (t.date_deadline-(now() at time zone 'UTC'))))/(3600*24)  as delay_endings_days
        """
        return select_str

    def _group_by(self):
        group_by_str = """
                GROUP BY
                    t.id,
                    create_date,
                    write_date,
                    date_assign,
                    date_end,
                    date_deadline,
                    date_last_stage_update,
                    t.user_id,
                    t.project_id,
                    t.priority,
                    t.milestone_id,
                    name,
                    t.company_id,
                    t.partner_id,
                    stage_id
        """
        return group_by_str
