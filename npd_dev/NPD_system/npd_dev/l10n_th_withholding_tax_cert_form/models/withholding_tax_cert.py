from odoo import models, api


class WithholdingTaxCert(models.Model):
    _inherit = "withholding.tax.cert"

    def _get_report_base_filename(self):
        self.ensure_one()
        return "WT Certificates - %s" % self.display_name

    def _compute_desc_type_other(self, lines, ttype, income_type):
        base_type_other = lines.filtered(
            lambda l: l.wt_cert_income_type in [income_type]
        ).mapped(ttype)
        base_type_other = [x or "" for x in base_type_other]
        desc = ", ".join(base_type_other)
        return desc

    def _group_wt_line(self, lines):
        groups = self.env["withholding.tax.cert.line"].read_group(
            domain=[("id", "in", lines.ids)],
            fields=["wt_cert_income_type", "base", "amount"],
            groupby=["wt_cert_income_type"],
            lazy=False,
        )
        return groups

    def format_number(self, number):
        return '{:,.2f}'.format(number)

    @staticmethod
    def unit_process(val):
        units = ["", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
        tens = ["", "สิบ", "ยี่สิบ", "สามสิบ", "สี่สิบ", "ห้าสิบ", "หกสิบ", "เจ็ดสิบ", "แปดสิบ", "เก้าสิบ"]
        unit = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน", "ล้าน"]

        length = len(val) > 1
        result = ''

        for index, current in enumerate(map(int, val)):
            if current:
                if index:
                    result = unit[index] + result

                if length and current == 1 and index == 0:
                    result += 'เอ็ด'
                elif index == 1 and current == 2:
                    result = 'ยี่' + result
                elif index != 1 or current != 1:
                    result = units[current] + result

        return result

    @staticmethod
    def thai_num2text(number):
        s_number = str(number)[::-1]
        n_list = [s_number[i:i + 6].rstrip("0") for i in range(0, len(s_number), 6)]
        result = WithholdingTaxCert.unit_process(n_list.pop(0))

        for i in n_list:
            result = WithholdingTaxCert.unit_process(i) + 'ล้าน' + result

        return result

    @staticmethod
    def amount_to_text_thai(amount):
        integer_part, decimal_part = "{:.2f}".format(amount).split(".")
        integer_text = WithholdingTaxCert.thai_num2text(int(integer_part))
        if int(decimal_part) > 0:
            decimal_text = WithholdingTaxCert.thai_num2text(int(decimal_part))
            return integer_text + "บาท" + decimal_text + "สตางค์"
        else:
            return integer_text + "บาทถ้วน"

    def amount_to_text_custom(self, amount):
        # ตรวจสอบจำนวนทศนิยม
        str_amount = "{:.4f}".format(amount)
        integer_part, decimal_part = str_amount.split(".")
        if len(decimal_part) == 4:
            # ตัดให้เหลือ 2 ตำแหน่ง
            amount = round(amount, 2)
        return self.amount_to_text_thai(amount)
