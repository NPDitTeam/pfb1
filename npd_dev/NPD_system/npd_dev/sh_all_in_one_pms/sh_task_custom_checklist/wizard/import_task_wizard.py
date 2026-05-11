# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, api, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from odoo.tools import ustr


class ImportSOCustomWizard(models.TransientModel):
    _name = "import.task.custom.cl.wizard"
    _description = "Import Task Wizard"

    @api.model
    def default_company(self):
        return self.env.company

    import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    file = fields.Binary(string="File", required=True)
    company_id = fields.Many2one(
        'res.company', 'Company', default=default_company, required=True)

    def show_success_msg(self, counter, skipped_line_no):
        # open the new success message box
        view = self.env.ref('sh_message.sh_message_wizard')
        context = dict(self._context or {})
        dic_msg = str(counter) + " Records imported successfully \n"
        if skipped_line_no:
            dic_msg = dic_msg + "\nNote:"
        for k, v in skipped_line_no.items():
            dic_msg = dic_msg + "\nRow No " + k + " " + v + " "
        context['message'] = dic_msg

        return {
            'name': 'Success',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sh.message.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    def import_task_apply(self):
        task_cl_obj = self.env['task.custom.checklist']
        if self:
            for rec in self:
                # For CSV
                if rec.import_type == 'csv':
                    counter = 1
                    skipped_line_no = {}
                    try:
                        file = str(base64.decodebytes(
                            rec.file).decode('utf-8'))
                        myreader = csv.reader(file.splitlines())
                        skip_header = True
                        created_task_cl = False
                        created_task_cl_list = []
                        for row in myreader:
                            try:
                                if skip_header:
                                    skip_header = False
                                    counter = counter + 1
                                    continue

                                if row[0] not in (None, "") and row[1] not in (None, ""):
                                    vals = {}
                                    if row[0] != '':
                                        vals.update({'name': row[0]})
                                    if row[1] != '':
                                        vals.update(
                                            {'description': row[1]})

                                        created_task_cl = task_cl_obj.create(
                                            vals)
                                        created_task_cl_list.append(
                                            created_task_cl.id)
                            except Exception as e:
                                skipped_line_no[str(
                                    counter)] = " - Value is not valid " + ustr(e)
                                counter = counter + 1
                                continue

                    except Exception as e:
                        raise UserError(
                            _("Sorry, Your csv file does not match with our format " + ustr(e)))

                    if counter > 1:
                        completed_records = len(created_task_cl_list)
                        res = self.show_success_msg(
                            completed_records, skipped_line_no)
                        return res

                # For Excel
                if rec.import_type == 'excel':
                    counter = 1
                    skipped_line_no = {}
                    try:
                        wb = xlrd.open_workbook(
                            file_contents=base64.decodebytes(rec.file))
                        sheet = wb.sheet_by_index(0)
                        skip_header = True
                        created_task_cl = False
                        created_task_cl_list = []
                        for row in range(sheet.nrows):
                            try:
                                if skip_header:
                                    skip_header = False
                                    counter = counter + 1
                                    continue

                                if sheet.cell(row, 0).value not in (None, "") and sheet.cell(row, 1).value not in (None, ""):
                                    vals = {}

                                    if sheet.cell(row, 0).value != '' and sheet.cell(row, 1).value != '':
                                        if sheet.cell(row, 0).value != '':
                                            vals.update(
                                                {'name': sheet.cell(row, 0).value})

                                        if sheet.cell(row, 1).value != '':
                                            vals.update(
                                                {'description': sheet.cell(row, 1).value})

                                        created_task_cl = task_cl_obj.create(
                                            vals)
                                        created_task_cl_list.append(
                                            created_task_cl.id)

                            except Exception as e:
                                skipped_line_no[str(
                                    counter)] = " - Value is not valid " + ustr(e)
                                counter = counter + 1
                                continue

                    except Exception as e:
                        raise UserError(
                            _("Sorry, Your excel file does not match with our format " + ustr(e)))

                    if counter > 1:
                        completed_records = len(created_task_cl_list)
                        res = self.show_success_msg(
                            completed_records, skipped_line_no)
                        return res
