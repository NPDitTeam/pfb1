import base64
import json
import logging
import re
import requests
from datetime import datetime

from odoo import fields, models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# Mapping: Odoo database name → expected company info (name, aliases for matching)
DB_COMPANY_MAP = {
    'NPD_S_Group_New_V2': {
        'name_th': 'บริษัท นภดล เอส กรุ๊ป จำกัด',
        'name_en': 'NOPPADOL S GROUP CO., LTD.',
        'keywords': ['นภดล เอส กรุ๊ป', 'นภดล เอส', 'NOPPADOL S GR', 'NOPPADOL S GROUP', 'NPD S GROUP'],
    },
    'NPD_Bangkok_New': {
        'name_th': 'บริษัท นภดล กรุงเทพ จำกัด',
        'name_en': 'NOPPADOL BANGKOK CO., LTD.',
        'keywords': ['นภดล กรุงเทพ', 'NOPPADOL BANGKOK', 'NPD BANGKOK'],
    },
    'NPD_Intertrading_New': {
        'name_th': 'บริษัท นภดล อินเตอร์เทรดดิ้ง จำกัด',
        'name_en': 'NOPPADOL INTERTRADING CO., LTD.',
        'keywords': ['นภดล อินเตอร์เทรดดิ้ง', 'นภดล อินเตอร์', 'NOPPADOL INTER', 'NOPPADOL INTERTRADING', 'NPD INTERTRADING'],
    },
    'NPD_Logistics_New': {
        'name_th': 'บริษัท เอ็นพีดี โลจิสติกส์ จำกัด',
        'name_en': 'NPD LOGISTICS CO., LTD.',
        'keywords': ['เอ็นพีดี โลจิสติกส์', 'NPD LOGISTICS', 'NPD LOGISTIC'],
    },
    'NPD_Steeltech_New': {
        'name_th': 'บริษัท เอ็นพีดี สตีลเทค จำกัด',
        'name_en': 'NPD STEELTECH CO., LTD.',
        'keywords': ['เอ็นพีดี สตีลเทค', 'NPD STEELTECH', 'NPD STEEL'],
    },
}


class AccountPaymentSlipDate(models.Model):
    _inherit = 'account.payment'

    slip_date_extracted = fields.Char(
        string='วันที่จากสลิป (AI)',
        readonly=True,
        copy=False,
        help='วันที่ที่ AI อ่านได้จากสลิปการโอนเงิน',
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

    def _get_expected_company_info(self):
        """Get expected company info based on current database name."""
        db_name = self.env.cr.dbname
        company_info = DB_COMPANY_MAP.get(db_name)
        return company_info, db_name

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
            "คุณเป็นผู้เชี่ยวชาญในการอ่านสลิปการโอนเงิน/ใบเสร็จ/สลิปธนาคาร\n"
            "กรุณาอ่านข้อมูลต่อไปนี้จากสลิปการโอนเงินในรูปภาพ:\n\n"
            "1. วันที่ทำรายการ (Transaction Date)\n"
            "2. ชื่อผู้รับเงิน (Recipient Name / To)\n\n"
            "กฎ:\n"
            "1. หาวันที่ทำรายการ (Transaction Date) จากสลิป\n"
            "2. ถ้ามีหลายวันที่ ให้เลือกวันที่ทำรายการโอนเงิน (ไม่ใช่วันที่พิมพ์สลิป)\n"
            "3. ถ้าเป็นปี พ.ศ. (Buddhist Era) ให้แปลงเป็น ค.ศ. (CE) โดยลบ 543\n"
            "4. หาชื่อผู้รับเงิน (To / ไปยัง / ผู้รับ / Recipient) ให้ดึงชื่อเต็มทั้งภาษาไทยและอังกฤษ\n"
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

    def _check_recipient_matches_company(self, recipient_name):
        """Check if the recipient name from the slip matches the expected company for this DB.

        Uses fuzzy/like matching: checks if any keyword from the expected company
        appears in the recipient name (case-insensitive, ignoring spaces).

        Returns: (is_match: bool, expected_company_name: str, db_name: str)
        """
        company_info, db_name = self._get_expected_company_info()

        if not company_info:
            # DB not in the map — skip validation, allow through
            _logger.warning(
                "Database '%s' not found in DB_COMPANY_MAP. Skipping recipient validation.", db_name
            )
            return True, db_name, db_name

        expected_name = company_info.get('name_th', '')
        recipient_upper = (recipient_name or '').upper().strip()
        recipient_normalized = re.sub(r'\s+', ' ', recipient_upper)

        # Check keywords (like matching)
        for keyword in company_info.get('keywords', []):
            keyword_upper = keyword.upper().strip()
            if keyword_upper in recipient_normalized:
                _logger.info(
                    "Recipient match FOUND: keyword '%s' found in '%s'",
                    keyword, recipient_name
                )
                return True, expected_name, db_name

        # Also check full Thai and English names
        name_th_upper = company_info.get('name_th', '').upper().strip()
        name_en_upper = company_info.get('name_en', '').upper().strip()

        if name_th_upper and name_th_upper in recipient_normalized:
            return True, expected_name, db_name
        if name_en_upper and name_en_upper in recipient_normalized:
            return True, expected_name, db_name

        # Also check reverse: recipient keyword in company names
        # This handles cases like slip shows "NOPPADOL S GR" and we have "นภดล เอส กรุ๊ป"
        # Split recipient into words and check if significant parts match
        recipient_words = recipient_normalized.split()
        for word in recipient_words:
            if len(word) < 3:
                continue
            for keyword in company_info.get('keywords', []):
                if word in keyword.upper():
                    _logger.info(
                        "Reverse match FOUND: recipient word '%s' in keyword '%s'",
                        word, keyword
                    )
                    return True, expected_name, db_name

        _logger.warning(
            "Recipient match FAILED: '%s' does not match expected company '%s' (DB: %s)",
            recipient_name, expected_name, db_name
        )
        return False, expected_name, db_name

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

    def action_extract_slip_date(self):
        """Main action: extract date from payment slip using AI and verify recipient."""
        self.ensure_one()

        if self.state != 'draft':
            raise UserError(_("สามารถใช้ฟังก์ชันนี้ได้เฉพาะเอกสารที่อยู่ในสถานะฉบับร่างเท่านั้น"))

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

        # Step 4: Validate recipient name against current DB company
        recipient_name = result.get('recipient_name', '')
        _logger.info("AI read recipient name: %s", recipient_name)

        if recipient_name:
            is_match, expected_name, db_name = self._check_recipient_matches_company(recipient_name)
            if not is_match:
                raise UserError(_(
                    "ชื่อผู้รับเงินในสลิปไม่ตรงกับบริษัทที่ใช้งานอยู่!\n\n"
                    "ชื่อผู้รับในสลิป: %s\n"
                    "บริษัทที่คาดหวัง (DB: %s): %s\n\n"
                    "กรุณาตรวจสอบว่าอัปโหลดสลิปถูกต้องหรือไม่"
                ) % (recipient_name, db_name, expected_name))
        else:
            # AI couldn't read recipient name — log warning but allow
            _logger.warning("AI could not read recipient name from slip. Skipping validation.")

        # Step 5: All checks passed — update date
        self.write({
            'date': parsed_date,
            'slip_date_extracted': date_str,
        })

        # Return success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('สำเร็จ'),
                'message': _('อ่านวันที่จากสลิปสำเร็จ: %s (ผู้รับ: %s)') % (date_str, recipient_name or '-'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }
