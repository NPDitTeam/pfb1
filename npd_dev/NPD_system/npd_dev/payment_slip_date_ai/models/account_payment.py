import base64
import json
import logging
import requests
from datetime import datetime

from odoo import fields, models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


class AccountPaymentSlipDate(models.Model):
    _inherit = 'account.payment'

    slip_date_extracted = fields.Char(
        string='วันที่จากสลิป (AI)',
        readonly=True,
        copy=False,
        help='วันที่ที่ AI อ่านได้จากสลิปการโอนเงิน',
    )

    slip_date_checked = fields.Boolean(
        string='ตรวจสอบวันที่จากสลิปแล้ว',
        default=False,
        readonly=True,
        copy=False,
        help='ต้องกดปุ่ม "ใช้วันที่จากสลิป" ก่อน จึงจะยืนยันเอกสารได้',
    )

    def _get_gemini_api_key(self):
        """Get Gemini API key from system parameters (shared with advance_clear_ai_check)."""
        api_key = self.env['ir.config_parameter'].sudo().get_param(
            'advance_clear_ai_check.gemini_api_key', default=''
        )
        if not api_key:
            raise UserError(_(
                "Gemini API Key is not configured.\n"
                "Please set it in Settings > Technical > System Parameters\n"
                "Key: advance_clear_ai_check.gemini_api_key"
            ))
        return api_key

    def _get_slip_attachments(self):
        """Get image attachments from chatter (เอกสารแนบ)."""
        self.ensure_one()
        image_mimes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp']

        # Get attachments linked directly to this payment
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'account.payment'),
            ('res_id', '=', self.id),
        ])

        # Also get attachments from mail messages (chatter)
        if hasattr(self, 'message_ids') and self.message_ids:
            msg_attachments = self.env['ir.attachment'].search([
                ('res_model', '=', 'mail.message'),
                ('res_id', 'in', self.message_ids.ids),
            ])
            attachments |= msg_attachments

        # Filter only image files
        image_attachments = attachments.filtered(
            lambda a: a.mimetype in image_mimes and a.datas
        )
        return image_attachments

    def _call_gemini_for_slip_info(self, attachments):
        """Call Gemini API to extract date AND recipient name from payment slip images.

        Returns dict: {
            'date': 'DD/MM/YYYY',
            'found': True/False,
            'recipient_name': 'ชื่อผู้รับเงิน',
            'recipient_found': True/False
        }
        """
        api_key = self._get_gemini_api_key()

        parts = []
        for idx, att in enumerate(attachments, 1):
            if att.datas:
                mime_type = att.mimetype or 'image/jpeg'
                image_data = att.datas.decode('utf-8') if isinstance(att.datas, bytes) else att.datas
                parts.append({
                    "text": "[รูปที่ %d] ชื่อไฟล์: %s" % (idx, att.name or 'unknown'),
                })
                parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_data,
                    }
                })

        prompt = (
            "คุณเป็นผู้เชี่ยวชาญในการอ่านสลิปการโอนเงิน/ใบเสร็จ/สลิปธนาคาร/"
            "ใบแจ้งการชำระเงิน (Payment Advice)\n"
            "กรุณาอ่านข้อมูลต่อไปนี้จากเอกสารในรูปภาพ:\n\n"
            "1. วันที่ทำรายการ (Transaction Date)\n"
            "2. ชื่อผู้รับเงิน (Recipient Name / To)\n\n"
            "กฎ:\n"
            "1. หาวันที่ทำรายการ (Transaction Date) จากเอกสาร\n"
            "2. ถ้ามีหลายวันที่ ให้เลือกตามลำดับความสำคัญ:\n"
            "   (ก) 'วันที่ทำรายการ' หรือ 'Transaction Date' — ใช้ค่านี้เป็นอันดับแรกเสมอ\n"
            "   (ข) ถ้าไม่มี (ก) ค่อยใช้ 'วันที่' / 'Date' ทั่วไป\n"
            "   *** ห้ามใช้ 'วันที่รายการมีผล / Value Date' หรือ 'อัปเดตล่าสุด / Last Updated' "
            "หรือ 'วันที่พิมพ์ / Print Date' ***\n"
            "3. ถ้าเป็นปี พ.ศ. (Buddhist Era) ให้แปลงเป็น ค.ศ. (CE) โดยลบ 543\n"
            "4. หาชื่อผู้รับเงิน (To / ไปยัง / ผู้รับ / Recipient) ให้ดึงชื่อเต็มทั้งภาษาไทยและอังกฤษ\n"
            "   - สำหรับ Payment Advice / ใบแจ้งการชำระเงิน: ผู้รับเงินอาจอยู่ในส่วน "
            "'รายละเอียดผู้รับเงิน / Recipient Details / Beneficiary' หรือ 'เรียน'\n"
            "5. ตอบกลับเป็น JSON format เท่านั้น\n\n"
            "ตอบกลับ JSON:\n"
            "{\n"
            '  "date": "DD/MM/YYYY",\n'
            '  "found": true,\n'
            '  "recipient_name": "ชื่อผู้รับเงินที่อ่านได้ (ทั้งไทยและอังกฤษ คั่นด้วย / ถ้ามีทั้งสองภาษา)",\n'
            '  "recipient_found": true\n'
            "}\n\n"
            "ถ้าไม่พบวันที่หรือชื่อผู้รับ ให้ set found/recipient_found เป็น false\n\n"
            "หมายเหตุ: DD/MM/YYYY เป็นรูปแบบ วัน/เดือน/ปี ค.ศ. เช่น 24/03/2026"
        )
        parts.append({"text": prompt})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json",
            },
        }

        headers = {"content-type": "application/json"}
        url = "%s?key=%s" % (GEMINI_API_URL, api_key)

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()

            candidates = result.get('candidates', [])
            if candidates:
                content = candidates[0].get('content', {})
                parts_resp = content.get('parts', [])
                if parts_resp:
                    text_result = parts_resp[0].get('text', '')
                    _logger.info("Gemini slip info response: %s", text_result)
                    try:
                        parsed = json.loads(text_result)
                        return parsed
                    except (json.JSONDecodeError, TypeError):
                        _logger.warning("Failed to parse Gemini response as JSON: %s", text_result)

            return {'date': '', 'found': False, 'recipient_name': '', 'recipient_found': False}

        except requests.exceptions.Timeout:
            raise UserError(_("Gemini API request timed out. Please try again."))
        except requests.exceptions.ConnectionError:
            raise UserError(_("Cannot connect to Gemini API. Please check your internet connection."))
        except requests.exceptions.HTTPError as e:
            error_msg = str(e)
            try:
                error_detail = e.response.json()
                error_msg = error_detail.get('error', {}).get('message', str(e))
            except Exception:
                pass
            raise UserError(_("Gemini API Error: %s") % error_msg)
        except Exception as e:
            raise UserError(_("Unexpected error calling Gemini API: %s") % str(e))

    def _parse_slip_date(self, date_str):
        """Parse date string DD/MM/YYYY to Python date object.

        Also handles:
        - DD-MM-YYYY
        - YYYY-MM-DD
        - Buddhist Era years (> 2500)
        """
        if not date_str:
            return None

        date_str = date_str.strip()

        # Try DD/MM/YYYY or DD-MM-YYYY
        for fmt in ['%d/%m/%Y', '%d-%m-%Y']:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Check if Buddhist Era (year > 2500)
                if dt.year > 2500:
                    dt = dt.replace(year=dt.year - 543)
                return dt.date()
            except ValueError:
                continue

        # Try YYYY-MM-DD
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            if dt.year > 2500:
                dt = dt.replace(year=dt.year - 543)
            return dt.date()
        except ValueError:
            pass

        return None

    def action_post(self):
        """Block confirmation unless the slip date has been extracted/checked first.

        The user MUST press the "ใช้วันที่จากสลิป" button (which runs
        action_extract_slip_date and sets slip_date_checked=True) before the
        payment can be posted/confirmed.

        Callers that auto-create+post payments programmatically (เช่นโมดูล
        account_voucher_npd ฟังก์ชันคืนเงินประกันค่าเช่า) สามารถข้ามการตรวจ
        ได้โดยส่ง context `skip_slip_date_check=True` เนื่องจากกรณีเหล่านี้
        ไม่มีสลิปแยกให้ AI อ่าน (เกิดจากการหักยอดในระบบ ไม่ใช่การโอนเงินจริง)

        Payment Method ที่ไม่มีสลิปจริง (ไม่ใช่การโอนเงิน) ก็ข้ามการตรวจอัตโนมัติ:
        - ประเภท 'cash' (เงินสด)
        - ชื่อ 'หักเงินประกันค่าเช่า' (หักจากเงินประกัน — ไม่มีสลิป)
        """
        if not self.env.context.get('skip_slip_date_check'):
            for payment in self:
                pm = payment.payment_method_one_id
                # จ่ายเงินสด / หักจากเงินประกัน → ไม่มีสลิป ข้ามได้
                if pm and (pm.type == 'cash' or pm.name == 'หักเงินประกันค่าเช่า'):
                    continue
                if not payment.slip_date_checked:
                    raise UserError(_(
                        "กรุณากดปุ่ม \"ใช้วันที่จากสลิป\" เพื่อตรวจสอบวันที่จากสลิปก่อน\n"
                        "จึงจะสามารถยืนยันเอกสารได้"
                    ))
        return super(AccountPaymentSlipDate, self).action_post()

    def action_draft(self):
        """Reset the slip check flag so the button must be pressed again
        before the payment can be confirmed once more."""
        res = super(AccountPaymentSlipDate, self).action_draft()
        self.write({'slip_date_checked': False})
        return res

    def action_extract_slip_date(self):
        """Main action: extract date from payment slip using AI and verify recipient."""
        self.ensure_one()

        # Step 1: Get image attachments
        attachments = self._get_slip_attachments()
        if not attachments:
            raise UserError(_(
                "ไม่พบรูปภาพสลิปในเอกสารแนบ\n"
                "กรุณาอัปโหลดรูปสลิปการโอนเงินในส่วนเอกสารแนบ (Log/Chatter) ก่อน"
            ))

        if len(attachments) > 1:
            raise UserError(_(
                "พบรูปภาพสลิป %d ไฟล์ในเอกสารแนบ\n"
                "กรุณาอัปโหลดสลิปการโอนเงินเพียง 1 ไฟล์เท่านั้น\n"
                "กรุณาลบสลิปที่ไม่ต้องการออกก่อนแล้วลองใหม่อีกครั้ง"
            ) % len(attachments))

        # Step 2: Call Gemini API to get date + recipient
        result = self._call_gemini_for_slip_info(attachments)

        # Step 3: Validate date
        if not result.get('found', False) or not result.get('date'):
            raise UserError(_(
                "AI ไม่สามารถอ่านวันที่จากสลิปได้\n"
                "กรุณาตรวจสอบว่ารูปสลิปชัดเจนและมีวันที่ปรากฏอยู่"
            ))

        date_str = result.get('date', '')
        parsed_date = self._parse_slip_date(date_str)

        if not parsed_date:
            raise UserError(_(
                "AI อ่านวันที่ได้เป็น '%s' แต่ไม่สามารถแปลงเป็นวันที่ได้\n"
                "กรุณาตรวจสอบรูปสลิปอีกครั้ง"
            ) % date_str)

        recipient_name = result.get('recipient_name', '')
        _logger.info("AI read recipient name: %s", recipient_name)

        # Step 4: All checks passed — mark as checked.
        # Only overwrite the payment date while still in draft. Once the payment
        # is posted, its date is locked to the posted journal entries and writing
        # it would raise "You cannot delete an item linked to a posted entry".
        vals = {
            'slip_date_extracted': date_str,
            'slip_date_checked': True,
        }
        if self.state == 'draft':
            vals['date'] = parsed_date
            message = _('อ่านวันที่จากสลิปสำเร็จ: %s (ผู้รับ: %s)') % (date_str, recipient_name or '-')
        else:
            message = _(
                'อ่านวันที่จากสลิปได้: %s (ผู้รับ: %s)\n'
                'เอกสารถูกลงบันทึกแล้ว จึงไม่เปลี่ยนวันที่ในเอกสาร'
            ) % (date_str, recipient_name or '-')
        self.write(vals)

        # Return success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('สำเร็จ'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }
