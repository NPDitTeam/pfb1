from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from collections import defaultdict
import requests
import logging
from datetime import date
_logger = logging.getLogger(__name__)


class StockAPITransfer(models.Model):
    _name = "stock.api.transfer"
    _description = "Stock Transfer via API"

    transfer_date = fields.Date(
        string="วันโยกสินค้า",
        default=lambda self: date.today(),
        required=True
    )
    note = fields.Text(string="หมายเหตุ")
    name = fields.Char(string="เลขอ้างอิง", required=True, copy=False, readonly=True, default="New")
    database_selection = fields.Selection(selection=lambda self: self._get_database_options(), string="เลือกฐานข้อมูล")
    location_id = fields.Many2one("stock.location", string="คลังปลายทาง")
    product_api_ids = fields.Many2many(
        "stock.api.transfer.product.name",
        string="สินค้า (API)",
        domain="[('is_visible_in_ui', '=', True)]"
    )
    location_api_id = fields.Many2one(
        "stock.api.transfer.location.name",
        string="คลังต้นทาง (API)",
        domain="[('is_visible_in_ui', '=', True)]"
    )
    line_ids = fields.One2many("stock.api.transfer.line", "transfer_id", string="รายการสินค้า", copy=True)

    state = fields.Selection([
        ("draft", "ร่าง"),
        ("waiting_approval", "รออนุมัติ"),
        ("approved", "อนุมัติแล้ว"),
        ("confirmed", "ยืนยันแล้ว"),
    ], default="draft")

    approval_id = fields.Many2one(
        "stock.transfer.approval",
        string="การอนุมัติ",
        readonly=True,
        copy=False,
    )
    approval_reason = fields.Text(
        related="approval_id.reason",
        string="เหตุผลการโยก",
        readonly=True,
    )
    approval_reject_note = fields.Text(
        related="approval_id.reject_note",
        string="หมายเหตุตีกลับ",
        readonly=True,
    )
    approver_id = fields.Many2one(
        related="approval_id.approver_id",
        string="ผู้อนุมัติ",
        readonly=True,
        store=True,
    )
    approval_state = fields.Selection(
        related="approval_id.state",
        string="สถานะอนุมัติ",
        readonly=True,
    )
    approval_attachment_ids = fields.Many2many(
        related="approval_id.attachment_ids",
        string="ไฟล์แนบ",
        readonly=True,
    )

    def _get_database_options(self):
        return [
            ('NPD_Bangkok_New', 'NPD_Bangkok_New'),
            ('NPD_S_Group_New_V2', 'NPD_S_Group_New_V2'),
            ('NPD_Intertrading_New', 'NPD_Intertrading_New'),
            ('NPD_Steeltech_New', 'NPD_Steeltech_New'),
            ('NPD_Logistics_New', 'NPD_Logistics_New'),
            ('NPD_Intertrading_New_NonVat', 'NPD_Intertrading_New_NonVat'),
            ('Test_NPD_Bangkok_New', 'Test_NPD_Bangkok_New'),
            ('test', 'test'),
        ]

    @api.onchange('database_selection')
    def _onchange_database_selection(self):
        if not self.database_selection:
            self.product_api_ids = [(5, 0, 0)]
            return

        stock_data = self._get_api_stock(self.database_selection)
        ProductModel = self.env['stock.api.transfer.product.name']

        ProductModel.search([]).write({'is_visible_in_ui': False})

        for item in stock_data:
            pname = item.get("product_name", "").strip()
            dcode = item.get("default_code", "").strip()

            if not pname or not dcode:
                continue

            existing_product = ProductModel.search([
                ('name', '=', pname),
                ('active_in_db', '=', self.database_selection)
            ], limit=1)

            if existing_product:
                existing_product.write({
                    'default_code': dcode,
                    'is_visible_in_ui': True
                })
            else:
                ProductModel.create({
                    'name': pname,
                    'default_code': dcode,
                    'active_in_db': self.database_selection,
                    'is_visible_in_ui': True
                })

        # ดึง location name จาก stock_data และสร้างใหม่ถ้ายังไม่มี (กรองเฉพาะคลังจริง)
        LocationModel = self.env['stock.api.transfer.location.name']
        LocationModel.search([]).write({'is_visible_in_ui': False})
        _logger.info("📦 stock_data items: %d | db: %s", len(stock_data), self.database_selection)

        seen_locations = set()
        for item in stock_data:
            loc_name = item.get("location", "").strip()
            if not loc_name or not loc_name.startswith("W"):
                continue
            if loc_name in seen_locations:
                continue
            seen_locations.add(loc_name)

            existing_loc = LocationModel.search([
                ('name', '=', loc_name),
                '|',
                ('active_in_db', '=', self.database_selection),
                ('active_in_db', '=', False),
            ], limit=1)
            if existing_loc:
                existing_loc.write({
                    'is_visible_in_ui': True,
                    'active_in_db': self.database_selection,
                })
            else:
                try:
                    LocationModel.create({
                        'name': loc_name,
                        'active_in_db': self.database_selection,
                        'is_visible_in_ui': True
                    })
                except Exception as e:
                    _logger.warning("‼️ ไม่สามารถสร้างคลังต้นทางใหม่ได้: %s | %s", loc_name, str(e))

        _logger.info("📍 คลังที่โหลดได้: %d รายการ → %s", len(seen_locations), seen_locations)
        self.product_api_ids = [(5, 0, 0)]
        self.location_api_id = False

    @api.onchange('location_api_id')
    def _onchange_location_api_filter_products(self):
        """เมื่อเลือกคลังต้นทาง กรองสินค้า (API) ให้แสดงเฉพาะสินค้าที่มีในคลังนั้น"""
        ProductModel = self.env['stock.api.transfer.product.name']

        if not self.location_api_id or not self.database_selection:
            # ถ้าไม่ได้เลือกคลัง ให้แสดงสินค้าทั้งหมดจาก database ที่เลือก
            return

        stock_data = self._get_api_stock(self.database_selection)
        source_location_name = self.location_api_id.name.strip().lower()

        # หาสินค้าที่มีอยู่ในคลังต้นทางที่เลือก
        product_codes_at_location = set()
        for item in stock_data:
            locname = item.get("location", "").strip().lower()
            if locname == source_location_name:
                pname = item.get("product_name", "").strip()
                dcode = item.get("default_code", "").strip()
                if pname and dcode:
                    product_codes_at_location.add((pname, dcode))

        _logger.info("📍 คลังที่เลือก: %s | สินค้าที่พบ: %d รายการ", self.location_api_id.name, len(product_codes_at_location))

        # ตั้งค่า is_visible_in_ui เฉพาะสินค้าที่อยู่ในคลังนั้น
        ProductModel.search([]).write({'is_visible_in_ui': False})
        for pname, dcode in product_codes_at_location:
            existing = ProductModel.search([
                ('name', '=', pname),
                ('active_in_db', '=', self.database_selection)
            ], limit=1)
            if existing:
                existing.write({'is_visible_in_ui': True})
            else:
                ProductModel.create({
                    'name': pname,
                    'default_code': dcode,
                    'active_in_db': self.database_selection,
                    'is_visible_in_ui': True
                })

        # เคลียร์สินค้าที่เลือกไว้เดิม (เพราะอาจไม่มีในคลังใหม่)
        self.product_api_ids = [(5, 0, 0)]

    @api.onchange('product_api_ids')
    def _warn_if_no_database_selected(self):
        if self.product_api_ids and not self.database_selection:
            return {
                'warning': {
                    'title': 'กรุณาเลือกฐานข้อมูล',
                    'message': 'คุณต้องเลือกฐานข้อมูลก่อน เพื่อโหลดรายการสินค้า (API)'
                }
            }

    def _find_local_product(self, default_code):
        """ค้นหา product.product ใน local db จาก default_code
        จับตรงตัวก่อน แล้วค่อย fallback เป็น ilike — กัน ilike ไปโดนรหัสอื่นที่มีรหัสนี้เป็นส่วนหนึ่ง"""
        if not default_code:
            return False
        Template = self.env['product.template']
        tmpl = Template.search([('default_code', '=', default_code)], limit=1)
        if not tmpl:
            tmpl = Template.search([('default_code', 'ilike', default_code)], limit=1)
        return tmpl.product_variant_id if tmpl else False

    def _get_local_stock(self):
        """ข้อมูลสต๊อกจาก DB ที่รันอยู่ ในรูปแบบเดียวกับที่ /api/get_stock คืนมา"""
        quants = self.env['stock.quant'].sudo().search([
            ('product_id.product_tmpl_id.route_ids.name', '=', 'ขอเบิก')
        ])
        total_quantities = defaultdict(float)
        for q in quants:
            total_quantities[q.product_id.id] += q.quantity

        return [{
            'product_id': q.product_id.id,
            'product_name': q.product_id.name or '',
            'location_id': q.location_id.id,
            'location': q.location_id.complete_name or '',
            'quantity': q.quantity,
            'default_code': q.product_id.default_code or '',
            'total_qty_all_locations': total_quantities[q.product_id.id],
        } for q in quants]

    def _get_api_stock(self, db_name):
        # DB เดียวกับที่รันอยู่ → อ่านจากเครื่องตรงๆ ไม่ต้องยิง HTTP
        # (เดิมยิงไป npderp.com เสมอ ทำให้ "คงเหลือ" ที่โชว์เป็นตัวเลขของอีกเซิร์ฟเวอร์ ไม่ตรงกับ DB นี้)
        if db_name == self.env.cr.dbname:
            return self._get_local_stock()

        try:
            session = requests.Session()
            login_response = session.post("https://npderp.com/web/session/authenticate", json={
                "jsonrpc": "2.0", "method": "call", "params": {
                    "db": db_name, "login": "Npd_admin", "password": "1234"
                }, "id": 1
            })
            session_id = login_response.cookies.get("session_id")
            headers = {"Content-Type": "application/json", "Cookie": f"session_id={session_id}"}
            response = session.post("https://npderp.com/api/get_stock", json={
                "db": db_name, "username": "Npd_admin", "password": "1234"
            }, headers=headers)
            return response.json().get("result", {}).get("result", [])
        except Exception as e:
            _logger.error("❌ ERROR _get_api_stock: %s", str(e))
            return []

    @api.onchange('product_api_ids', 'location_api_id')
    def _onchange_product_location_api(self):
        self.line_ids = [(5, 0, 0)]

        if not self.product_api_ids or not self.location_api_id or not self.database_selection:
            return

        stock_data = self._get_api_stock(self.database_selection)
        if not isinstance(stock_data, list):
            _logger.error("❌ รูปแบบข้อมูล API ผิดพลาด: ไม่ใช่ list")
            return

        selected_codes_map = {
            p.default_code.strip().lower(): p.name
            for p in self.product_api_ids if p.default_code
        }
        selected_codes = set(selected_codes_map.keys())
        source_location_name = self.location_api_id.name.strip().lower()

        _logger.info("🧾 product_api_ids = %s", [(p.name, p.default_code) for p in self.product_api_ids])
        _logger.info("📌 selected_codes = %s", selected_codes)
        _logger.info("🏷️ source_location_name = %s", source_location_name)

        _logger.info("🔍 START CHECKING STOCK DATA (total items: %d)", len(stock_data))

        # แสดงคลังทั้งหมดที่ API คืนมา เพื่อ debug
        api_locations = set(item.get("location", "").strip() for item in stock_data if item.get("location"))
        _logger.info("📍 คลังทั้งหมดจาก API: %s", api_locations)

        # แสดงสินค้าที่ตรงกับ code ที่เลือก ไม่ว่าจะอยู่คลังไหน
        for item in stock_data:
            code = item.get("default_code", "").strip().lower()
            if code in selected_codes:
                _logger.info("🎯 พบสินค้าที่เลือก: product=%s | code=%s | loc=%s | qty=%.2f",
                             item.get("product_name"),
                             item.get("default_code"),
                             item.get("location"),
                             item.get("quantity", 0.0))

        # ตรวจสอบว่าคลังที่เลือกมีอยู่ใน API ไหม
        api_locations_lower = set(loc.lower() for loc in api_locations)
        if source_location_name not in api_locations_lower:
            _logger.warning("⚠️ คลังต้นทางที่เลือก '%s' ไม่มีใน API! คลังที่มี: %s",
                            self.location_api_id.name.strip(), api_locations)

        line_vals = []
        seen_keys = set()
        found_codes = set()

        for item in stock_data:
            default_code = item.get("default_code", "").strip()
            product_name = item.get("product_name", "").strip()
            normalized_code = default_code.lower()
            locname = item.get("location", "").strip().lower()
            qty = item.get("quantity", 0.0)
            lid = item.get("location_id")
            key = (normalized_code, lid)

            if normalized_code in selected_codes and locname == source_location_name and key not in seen_keys:
                seen_keys.add(key)
                found_codes.add(normalized_code)

                line_vals.append((0, 0, {
                    'product_name': product_name,
                    'location_api_id': self.location_api_id,
                    'location_id': lid,
                    'default_code': default_code,
                    'available_qty': qty,
                    'request_qty': 0.0,
                    'destination_location_id': self.location_id.id,
                    'status': 'รอดำเนินการ'
                }))

        self.line_ids = line_vals
        _logger.info("✅ line_vals = %s", line_vals)

        missing_names = [selected_codes_map[code] for code in selected_codes if code not in found_codes]
        if not line_vals and missing_names:
            return {
                'warning': {
                    'title': 'ไม่มีสินค้าในคลังต้นทาง',
                    'message': 'ไม่พบสินค้าในคลังต้นทางนี้:\n- ' + "\n- ".join(missing_names)
                }
            }

    def action_send_approval(self):
        """เปิด popup ส่งขออนุมัติ"""
        self.ensure_one()
        if not self.line_ids:
            raise UserError("ไม่สามารถส่งขออนุมัติได้ เนื่องจากไม่มีรายการสินค้า\nกรุณาเลือกสินค้า (API) และคลังต้นทางให้ถูกต้อง")
        if not any(line.request_qty > 0 for line in self.line_ids):
            raise UserError("กรุณาระบุจำนวนขอตัดอย่างน้อย 1 รายการ")
        approver_group = self.env.ref('stock_api_transfer.group_stock_transfer_approver')
        approver_user_ids = self.env['res.users'].search([
            ('groups_id', 'in', [approver_group.id])
        ]).ids
        return {
            'name': 'ส่งขออนุมัติการโยกสินค้า',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.transfer.approval.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_transfer_id': self.id,
                'approver_user_ids': approver_user_ids,
            },
        }

    def action_approve(self):
        """อนุมัติการโยกสินค้า"""
        self.ensure_one()
        if self.approval_id:
            self.approval_id.action_approve()

    def action_open_reject_wizard(self):
        """เปิด popup ตีกลับ"""
        self.ensure_one()
        return {
            'name': 'ตีกลับการโยกสินค้า',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.transfer.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_transfer_id': self.id,
            },
        }

    def unlink(self):
        for rec in self:
            if rec.state == 'confirmed':
                raise UserError("ไม่สามารถลบเอกสารที่ยืนยันแล้วได้")
        return super(StockAPITransfer, self).unlink()

    # ------------------------------------------------------------------
    # โยกสต๊อกภายใน DB ที่รันอยู่ (database_selection == cr.dbname)
    # ------------------------------------------------------------------
    def _get_onhand_qty(self, product, location):
        """คงเหลือจริงของสินค้าที่คลังนั้น (อ่าน stock.quant ตรงๆ แบบเดียวกับที่ API get_stock ทำ)"""
        if not product or not location:
            return 0.0
        quants = self.env['stock.quant'].sudo().search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
        ])
        return sum(quants.mapped('quantity'))

    def _get_internal_picking_type(self, source_location):
        """ประเภทการโอนแบบ internal ของบริษัทเดียวกับคลังต้นทาง
        เลือกคลังสินค้าที่ครอบคลุมคลังต้นทางก่อน ถ้าไม่เจอค่อยใช้ตัวแรกของบริษัทนั้น"""
        domain = [('code', '=', 'internal')]
        if source_location.company_id:
            domain.append(('company_id', '=', source_location.company_id.id))
        picking_types = self.env['stock.picking.type'].sudo().search(domain)
        src_path = source_location.parent_path or ''
        for picking_type in picking_types:
            view_path = picking_type.warehouse_id.view_location_id.parent_path or ''
            if view_path and src_path.startswith(view_path):
                return picking_type
        return picking_types[:1]

    def _create_internal_picking(self, product, source_location, dest_location, qty):
        """สร้าง stock.picking แบบ internal แล้ว validate ทันที — คืน picking ที่เสร็จแล้ว"""
        picking_type = self._get_internal_picking_type(source_location)
        if not picking_type:
            raise UserError("ไม่พบประเภทการโอน (internal) สำหรับบริษัทของคลัง %s"
                            % source_location.complete_name)

        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,
            'location_dest_id': dest_location.id,
            'origin': self.name,
            'move_lines': [(0, 0, {
                'name': product.display_name or self.name,
                'product_id': product.id,
                'product_uom_qty': qty,
                'product_uom': product.uom_id.id,
                'location_id': source_location.id,
                'location_dest_id': dest_location.id,
                'picking_type_id': picking_type.id,
                'company_id': picking_type.company_id.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_lines:
            move.quantity_done = move.product_uom_qty
        res = picking.with_context(skip_immediate=True, skip_backorder=True).button_validate()
        if res is not True:
            raise ValidationError(
                "ไม่สามารถยืนยันใบโอน %s ได้อัตโนมัติ กรุณาตรวจสอบเอกสารในเมนูการดำเนินการ" % picking.name)
        _logger.info("✅ สร้างและยืนยันใบโอน: %s", picking.name)
        return picking

    def _run_local_transfer(self, lines, reverse=False):
        """โยกสต๊อกจริงใน DB ที่รันอยู่ (reverse=True คือคืนของ ปลายทาง → ต้นทาง)"""
        if not self.location_id:
            raise UserError("กรุณาเลือกคลังปลายทาง")

        Location = self.env['stock.location'].sudo()
        jobs = []
        shortages = []
        for line in lines:
            src_location = Location.browse(line.location_id).exists()
            if not src_location:
                raise UserError("ไม่พบคลังต้นทาง (id=%s) ของ %s ในฐานข้อมูลนี้"
                                % (line.location_id, line.product_name))
            product = self._find_local_product(line.default_code)
            if not product:
                raise UserError("ไม่พบสินค้ารหัส %s ในฐานข้อมูลนี้" % line.default_code)

            src, dest = (self.location_id, src_location) if reverse else (src_location, self.location_id)
            if src == dest:
                raise UserError("คลังต้นทางและคลังปลายทางเป็นคลังเดียวกัน (%s)" % dest.complete_name)

            avail = self._get_onhand_qty(product, src)
            if line.request_qty > avail:
                shortages.append("• %s @ %s — ขอ %.2f / คงเหลือ %.2f"
                                 % (product.display_name, src.complete_name, line.request_qty, avail))
            jobs.append((line, product, src, dest, src_location))

        if shortages:
            raise UserError("สต๊อกไม่พอสำหรับ:\n" + "\n".join(shortages))

        for line, product, src, dest, src_location in jobs:
            picking = self._create_internal_picking(product, src, dest, line.request_qty)
            line.write({
                'status': 'รอดำเนินการ' if reverse else 'สำเร็จ',
                'available_qty': self._get_onhand_qty(product, src_location),
            })
            _logger.info("📦 %s %s: %s → %s %.2f (%s)",
                         "คืนของ" if reverse else "โอน", product.display_name,
                         src.complete_name, dest.complete_name, line.request_qty, picking.name)

    # ------------------------------------------------------------------
    # Confirm
    # ------------------------------------------------------------------
    def action_confirm(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError("ต้องได้รับการอนุมัติก่อนจึงจะยืนยันการโอนได้")

        lines = self.line_ids.filtered(lambda l: l.request_qty > 0)
        if not lines:
            raise UserError("ไม่มีรายการที่ระบุจำนวนขอตัด")
        if not self.location_id:
            raise UserError("กรุณาเลือกคลังปลายทาง")

        if self.name == 'New':
            today = fields.Date.context_today(self)
            seq_date = today.strftime('%Y-%m-%d')  # ex. '2025-04-22'
            self.name = self.env['ir.sequence'].with_context(
                ir_sequence_date=seq_date
            ).next_by_code('stock.api.transfer') or 'New'

        # ดึงชื่อ database ปัจจุบันที่กำลังรัน Odoo ฝั่ง local
        current_db_name = self.env.cr.dbname
        if self.database_selection == current_db_name:
            # DB เดียวกับที่รันอยู่ → ทำในเครื่องตรงๆ ไม่ต้องยิง HTTP
            # (เดิมโยนงานให้ npderp.com เสมอ แล้วข้ามการเขียน local เพราะถือว่า "DB เดียวกัน = API จัดการแล้ว"
            #  ซึ่งจริงเฉพาะตอนโมดูลรันอยู่บน npderp.com — DB ชื่อเดียวกันบนเครื่องอื่นจึงไม่ถูกแตะเลย)
            self._run_local_transfer(lines)
        else:
            self._confirm_via_api(lines)

        self.write({"state": "confirmed"})

    def _confirm_via_api(self, lines):
        """โยกข้าม DB: ให้เซิร์ฟเวอร์ต้นทางตัดสต๊อกผ่าน API แล้วเติมสต๊อกปลายทางใน DB นี้"""
        transfers = [{
            'default_code': line.default_code,
            'source_location_id': line.location_id,
            'qty': line.request_qty,
        } for line in lines]

        try:
            # 🔐 STEP 1: Login เพื่อรับ session_id
            login_url = "https://npderp.com/web/session/authenticate"
            transfer_url = "https://npderp.com/api/transfer_stock"

            # login_url = "https://npderp.com/web/session/authenticate"
            # transfer_url = "https://npderp.com/api/transfer_stock"

            session = requests.Session()
            login_payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "db": self.database_selection,
                    "login": "Npd_admin",
                    "password": "1234"
                },
                "id": 1
            }

            login_response = session.post(login_url, json=login_payload)
            session_id = login_response.cookies.get("session_id")

            headers = {
                "Content-Type": "application/json",
                "Cookie": f"session_id={session_id}"
            }

            payload = {
                "db": self.database_selection,
                "username": "Npd_admin",  # optional
                "password": "1234",  # optional
                "transfers": transfers
            }

            response = session.post(transfer_url, json=payload, headers=headers)
            result = response.json()


            # JSON-RPC error (exception ฝั่งเซิร์ฟเวอร์) จะไม่มี key "result" เลย
            if result.get("error"):
                err = result["error"]
                msg = (err.get("data") or {}).get("message") or err.get("message") or str(err)
                raise ValidationError("❌ API ตอบกลับเป็น error: %s" % msg)

            # ✅ แก้จุดสำคัญ: เช็คสถานะภายใน "result"
            api_result = result.get("result", {})
            status_code = api_result.get("status", 0)
            if status_code != 200:
                _logger.error("❌ API Returned Error: %s", result)
                raise ValidationError(
                    api_result.get("error", "❌ ไม่สามารถตัดสต๊อกได้ (ไม่พบสาเหตุจาก API)"))

            # API คืน key 'documents' (เวอร์ชันเก่าคืน 'pickings') — ถ้ามี key แต่ว่างเปล่า
            # แปลว่าตอบ 200 ทั้งที่ไม่ได้สร้างเอกสารตัดสต๊อกเลย (เช่นหารหัสสินค้าที่ต้นทางไม่เจอ)
            documents = api_result.get("documents", api_result.get("pickings"))
            if documents is None:
                _logger.warning("⚠️ API ไม่ได้คืนรายการเอกสาร ตรวจสอบไม่ได้ว่าตัดสต๊อกจริงหรือไม่: %s", result)
            elif not documents:
                raise ValidationError(
                    "API ตอบสำเร็จแต่ไม่ได้สร้างเอกสารตัดสต๊อกเลย "
                    "(มักเกิดจากหารหัสสินค้าที่ต้นทางไม่พบ) — ยกเลิกการโอน")
            elif len(documents) != len(lines):
                # controller ฝั่งต้นทางใช้ continue ข้ามบรรทัดที่มีปัญหาแล้วยังตอบ 200
                # ถ้าปล่อยผ่าน จะเติมสต๊อกปลายทางครบทุกบรรทัดทั้งที่ต้นทางตัดไม่ครบ
                raise ValidationError(
                    "API ตัดสต๊อกได้ไม่ครบ (ขอ %d รายการ สำเร็จ %d รายการ: %s) — ยกเลิกการโอนทั้งใบ"
                    % (len(lines), len(documents), documents))
            else:
                _logger.info("✅ API TRANSFER SUCCESS: %s", documents)

            # ✅ อัปเดตสถานะรายการย่อย + เติมสต๊อกฝั่งปลายทางใน DB นี้
            for line in lines:
                new_qty = line.available_qty - line.request_qty
                line.write({
                    'status': 'สำเร็จ',
                    'available_qty': new_qty if new_qty >= 0 else 0.0  # ป้องกันติดลบ
                })
                product = self._find_local_product(line.default_code)
                if not product:
                    _logger.warning("⚠️ ไม่พบสินค้า local สำหรับ %s - ข้ามการเติมสต๊อก", line.default_code)
                    continue

                quant = self.env['stock.quant'].sudo().search([
                    ('product_id', '=', product.id),
                    ('location_id', '=', line.destination_location_id.id)
                ], limit=1)

                if quant:
                    quant.quantity += line.request_qty
                    _logger.info("📦 เติมสต๊อกที่คลังปลายทาง: %s เพิ่ม %.2f", line.product_name,
                                 line.request_qty)
                else:
                    self.env['stock.quant'].sudo().create({
                        'product_id': product.id,
                        'location_id': line.destination_location_id.id,
                        'quantity': line.request_qty,
                    })
                    _logger.info("📦 สร้างและเติมสต๊อกใหม่ที่คลังปลายทาง: %s = %.2f", line.product_name,
                                 line.request_qty)

        except ValidationError:
            raise
        except Exception as e:
            _logger.error("❌ TRANSFER FAILED: %s", str(e))
            raise ValidationError("❌ ไม่สามารถตัดสต๊อกได้: %s" % str(e))

    def action_cancel(self):
        self.ensure_one()
        if not self.env.user.has_group('stock_api_transfer.group_stock_transfer_approver'):
            raise UserError("เฉพาะผู้อนุมัติเท่านั้นที่สามารถยกเลิกได้")
        if self.state != "confirmed":
            return

        lines = self.line_ids.filtered(lambda l: l.request_qty > 0)
        current_db_name = self.env.cr.dbname
        if self.database_selection == current_db_name:
            # DB เดียวกับที่รันอยู่ → คืนของด้วยใบโอนย้อนกลับ ปลายทาง → ต้นทาง
            self._run_local_transfer(lines, reverse=True)
        else:
            self._cancel_via_api(lines)

        self.write({'state': 'draft'})

    def _cancel_via_api(self, lines):
        """คืนสต๊อกข้าม DB: ให้ API คืนของที่ต้นทาง แล้วตัดสต๊อกปลายทางออกจาก DB นี้"""
        rollback_data = [{
            "source_location_id": line.location_id,
            "default_code": line.default_code,
            "qty": line.request_qty,
        } for line in lines]

        try:
            # STEP 1: Login เพื่อดึง session_id
            login_url = "https://npderp.com/web/session/authenticate"
            rollback_url = "https://npderp.com/api/rollback_stock"
            # login_url = "https://npderp.com/web/session/authenticate"
            # rollback_url = "https://npderp.com/api/rollback_stock"
            session = requests.Session()

            login_payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "db": self.database_selection,
                    "login": "Npd_admin",
                    "password": "1234"
                },
                "id": 1
            }
            login_response = session.post(login_url, json=login_payload)
            session_id = login_response.cookies.get("session_id")

            if not session_id:
                raise Exception("ไม่สามารถเข้าสู่ระบบ API ได้ (ไม่มี session_id)")

            headers = {
                "Content-Type": "application/json",
                "Cookie": f"session_id={session_id}"
            }

            # STEP 2: เรียก API rollback พร้อมส่ง session
            payload = {
                "db": self.database_selection,
                "transfers": rollback_data
            }

            response = session.post(rollback_url, json=payload, headers=headers)

            # ตรวจสอบการตอบกลับ
            result = response.json()
            _logger.info("✅ API ROLLBACK RESPONSE: %s", result)

            # JSON-RPC error (exception ฝั่งเซิร์ฟเวอร์) จะไม่มี key "result" เลย
            if result.get("error"):
                err = result["error"]
                raise Exception((err.get("data") or {}).get("message") or err.get("message") or str(err))

            # ป้องกัน error จาก key ไม่ตรงหรือไม่มี status
            api_result = result.get("result", {})
            status = result.get("status") or api_result.get("status")
            pickings = result.get("pickings") or api_result.get("pickings")

            if int(status or 0) != 200:
                raise Exception(api_result.get("error") or result.get("error") or "Rollback failed")

            # คืนของได้ไม่ครบทุกบรรทัด = ห้ามตัดสต๊อกปลายทางออก ไม่งั้นของหายทั้งสองฝั่ง
            if pickings is not None and len(pickings) != len(lines):
                raise Exception("คืนของได้ไม่ครบ (ขอ %d รายการ สำเร็จ %d รายการ: %s)"
                                % (len(lines), len(pickings), pickings))

            _logger.info("🔄 ROLLBACK SUCCESS: %s", pickings)

        except Exception as e:
            _logger.error("❌ ROLLBACK FAILED: %s", str(e))
            raise UserError("ยกเลิกสต๊อกไม่สำเร็จ: %s" % str(e))

        # ✅ ตัดสต๊อกปลายทางที่เคยเติมไว้ใน DB นี้ออก
        for line in lines:
            line.write({
                'status': 'รอดำเนินการ',
                'available_qty': line.available_qty + line.request_qty,
            })
            if not line.destination_location_id:
                _logger.warning("⚠️ ไม่มีคลังปลายทาง จึงไม่สามารถ rollback stock ได้สำหรับ %s",
                                line.product_name)
                continue

            product = self._find_local_product(line.default_code)
            if not product:
                _logger.warning("⚠️ ไม่พบสินค้า local สำหรับ %s - ข้ามการ rollback", line.default_code)
                continue

            quant = self.env['stock.quant'].sudo().search([
                ('product_id', '=', product.id),
                ('location_id', '=', line.destination_location_id.id)
            ], limit=1)

            if quant:
                quant.quantity -= line.request_qty
                if quant.quantity < 0:
                    quant.quantity = 0.0
                _logger.info("🔴 ลบ stock ปลายทาง: %s -%.2f", line.product_name, line.request_qty)
            else:
                _logger.warning("❌ ไม่พบ stock.quant สำหรับ %s", line.product_name)


class StockAPITransferProductName(models.Model):
    _name = 'stock.api.transfer.product.name'
    _description = 'ชื่อสินค้าจาก API'

    name = fields.Char(string='ชื่อสินค้า', required=True)
    default_code = fields.Char(string='รหัสสินค้า', required=True)

    active_in_db = fields.Char(string='จากฐานข้อมูล')
    is_visible_in_ui = fields.Boolean(string='แสดงใน UI', default=False)

    _sql_constraints = [
        ('name_db_unique', 'unique(name, active_in_db)', 'ชื่อสินค้าซ้ำในฐานข้อมูลเดียวกันไม่ได้'),
    ]

