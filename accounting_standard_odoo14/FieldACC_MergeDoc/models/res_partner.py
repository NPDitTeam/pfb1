from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class ResCompany(models.Model):
    _inherit = 'res.partner'

    tax_branch_name = fields.Char(string='Tax Branch Name', readonly=True,
                                  compute='_compute_tax_branch_name')
    tax_branch_eng_name = fields.Char(string='Tax Branch Name', readonly=True,
                                      compute='_compute_tax_branch_eng_name')

    @api.depends('branch')
    def _compute_tax_branch_name(self):
        for company in self:
            branch_code = company.branch
            if branch_code:
                # Convert to string in case it's stored as an integer
                branch_code_str = str(branch_code)
                if branch_code_str == "00000":
                    company.tax_branch_name = "สำนักงานใหญ่"
                elif len(branch_code_str) == 5 and branch_code_str.startswith('0'):
                    # Remove leading zeros and prefix with 'สาขาที่ '
                    branch_number = int(branch_code_str)  # Convert to integer to remove leading zeros
                    company.tax_branch_name = "สาขาที่ {}".format(branch_number)
                else:
                    company.tax_branch_name = "Unknown format"
            else:
                company.tax_branch_name = False  # Or set to a default value if appropriate

    @api.depends('branch')
    def _compute_tax_branch_eng_name(self):
        for company in self:
            branch_code = company.branch
            if branch_code:
                # Convert to string in case it's stored as an integer
                branch_code_str = str(branch_code)
                if branch_code_str == "00000":
                    company.tax_branch_eng_name = "Head Office"
                elif len(branch_code_str) == 5 and branch_code_str.startswith('0'):
                    # Remove leading zeros and prefix with 'สาขาที่ '
                    branch_number = int(branch_code_str)  # Convert to integer to remove leading zeros
                    company.tax_branch_eng_name = "Branch No. {}".format(branch_number)
                else:
                    company.tax_branch_eng_name = "Unknown format"
            else:
                company.tax_branch_eng_name = False  # Or set to a default value if appropriate
