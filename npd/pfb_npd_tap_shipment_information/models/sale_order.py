import requests
import logging
import math
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ShipmentInformation(models.Model):
    _inherit = 'sale.order'

    delivery_type = fields.Selection(
        string='ประเภทการจัดส่ง',
        selection=[
            ('customer', 'จัดส่งไปยังลูกค้า'),
            ('branch', 'จัดส่งมายังสาขา'),
        ],
        default='customer',
        required=True,
        tracking=True
    )

    pickup_location = fields.Char(string='ต้นทาง')
    destination = fields.Char(string='ปลายทาง')
    vehicle_type_id = fields.Many2one('shipping.cost', string='ประเภทรถ')

    distance_km = fields.Float(string='ระยะทาง (km)', compute='_compute_distance', store=True)
    shipping_cost_raw = fields.Float(
        string='ค่าขนส่งก่อนปัดเศษ',
        compute='_compute_shipping_cost',
        store=True,
        readonly=False
    )

    shipping_cost = fields.Float(string='ค่าขนส่งหลังปัดเศษ', compute='_compute_shipping_cost', store=True,
                                 readonly=True)

    use_special_delivery_zero = fields.Boolean(
        string='ใช้ค่าขนส่งพิเศษที่เป็น 0',
        default=False,
        help='ติ๊กเพื่อใช้ค่าขนส่งพิเศษเป็น 0'
    )

    shipping_cost_m = fields.Float(string='ค่าขนส่งพิเศษ', store=True)
    delivery_employee_id = fields.Many2one('hr.employee', string='พนักงานส่งของ')
    license_plate_id = fields.Many2one(
        'fleet.license_plate',
        string='ป้ายทะเบียนรถ',
        domain=[('active', '=', True)],
    )

    # ========== ฟิลด์ใหม่: ค่าเที่ยวและค่าเบี้ยเลี้ยง ==========
    trip_allowance = fields.Float(
        string='ค่าเที่ยว (บาท)',
        compute='_compute_trip_allowance',
        store=True,
        readonly=True  # readonly เพื่อป้องกันการแก้ไขโดยตรง
    )

    daily_allowance = fields.Float(
        string='ค่าเบี้ยเลี้ยง (บาท)',
        compute='_compute_daily_allowance',
        store=True,
        readonly=True  # readonly เพื่อป้องกันการแก้ไขโดยตรง
    )

    # ========== ส่วนของค่าน้ำมัน ==========
    fuel_price_per_liter = fields.Float(string='ค่าน้ำมันเชื้อเพลิง (บาท/ลิตร)',
                                        related='vehicle_type_id.fuel_price_per_liter', store=True, readonly=False)
    fuel_consumption_rate = fields.Float(string='อัตราสิ้นเปลืองเชื้อเพลิง (กม./ลิตร)',
                                         related='vehicle_type_id.fuel_consumption_rate', store=True, readonly=False)
    fuel_used_per_trip = fields.Float(string='จำนวนน้ำมันที่ใช้ต่อการเดินทางไป-กลับ (ลิตร)',
                                      compute='_compute_fuel_used', store=True)
    fuel_cost_per_trip = fields.Float(string='ค่าน้ำมันเที่ยวไปกลับรอบนี้ (บาท)', compute='_compute_fuel_cost',
                                      store=True)

    # ========== ส่วนของค่าเสื่อมราคา ==========
    vehicle = fields.Float(string='ต้นทุนค่ารถ', related='vehicle_type_id.vehicle', store=True, readonly=False)
    vehicle_cost = fields.Float(string='ต้นทุนค่ารถดอกเบี้ย ร้อยละ 12 บ./ปี (บาท)', compute='_compute_vehicle_cost',
                                store=True)
    salvage_value = fields.Float(string='มูลค่าซาก (บาท)', related='vehicle_type_id.salvage_value', store=True,
                                 readonly=False)
    depreciation_period = fields.Integer(string='ระยะเวลาค่าเสื่อมราคา (ปี)',
                                         related='vehicle_type_id.depreciation_period', store=True, readonly=False)
    depreciation_per_trip = fields.Float(string='ค่าเสื่อมตัวรถต่อรอบ (บาท)', compute='_compute_depreciation_per_trip',
                                         store=True)

    # ค่าใช้จ่ายประจำปี
    annual_vehicle_tax_y = fields.Float(string='ค่าภาษีป้ายวงกลม (บาท/ปี)',
                                        related='vehicle_type_id.annual_vehicle_tax_y', store=True, readonly=False)
    annual_vehicle_tax = fields.Float(string='ค่าภาษีป้ายวงกลม (บาท/ปี)', compute='_compute_annual_vehicle_tax',
                                      store=True)
    annual_insurance_class2 = fields.Float(string='ค่าเบี้ยประกันชั้น',
                                           related='vehicle_type_id.annual_insurance_class2', store=True,
                                           readonly=False)
    annual_insurance_class1 = fields.Float(string='ประกันชั้น 1 รถยนต์ (บาท/ปี)',
                                           compute='_compute_annual_insurance_class1', store=True)
    annual_compulsory_insurance1 = fields.Float(string='ค่าประกัน พรบ',
                                                related='vehicle_type_id.annual_compulsory_insurance1', store=True,
                                                readonly=False)
    annual_compulsory_insurance = fields.Float(string='ค่าประกัน พรบ. (บาท/ปี)',
                                               compute='_compute_annual_compulsory_insurance', store=True)
    total_depreciation_per_trip = fields.Float(string='รวมค่าเสื่อมต่างๆต่อรอบไปกลับ (บาท)',
                                               compute='_compute_total_depreciation_per_trip', store=True)

    # ========== ส่วนของค่าแรงงาน ==========
    labor_costs = fields.Integer(string='ค่าแรง', related='vehicle_type_id.labor_costs', store=True, readonly=False)
    working_days_per_month = fields.Integer(string='จำนวนวันทำงานต่อเดือน',
                                            related='vehicle_type_id.working_days_per_month', store=True,
                                            readonly=False)
    driver_salary = fields.Float(string='เงินเดือน (บาท/เดือน)', related='vehicle_type_id.driver_salary', store=True,
                                 readonly=False)
    maintenance_cost = fields.Float(string='ค่าซ่อมบำรุง (บาท/เดือน)', related='vehicle_type_id.maintenance_cost',
                                    store=True, readonly=False)
    trips_per_day = fields.Integer(string='จำนวนรอบที่วิ่ง/วัน', related='vehicle_type_id.trips_per_day', store=True,
                                   readonly=False)
    labor_cost_per_trip = fields.Float(string='คิดค่าแรงให้ พนง.ขับรถต่อเที่ยว (บาท)',
                                       related='vehicle_type_id.labor_cost_per_trip', store=True, readonly=False)

    # ========== ค่าใช้จ่ายอื่นๆ ==========
    other_expenses = fields.Float(string='ค่าใช้จ่ายอื่นๆเช่น ค่าโทรศัพท์ ค่าเอกสาร (บาท/รอบ)',
                                  related='vehicle_type_id.other_expenses', store=True, readonly=False)
    total_labor_per_trip = fields.Float(string='ค่าแรงต่อรอบไปกลับ (บาท)', compute='_compute_total_labor_per_trip',
                                        store=True)

    # ========== สรุปต้นทุนและกำไร ==========
    total_cost_per_trip = fields.Float(
        string='ราคาต้นทุน (บาท/รอบ)',
        compute='_compute_total_cost_per_trip',
        store=True
    )
    profit_per_trip = fields.Float(string='กำไร (บาท/รอบ)', compute='_compute_profit_per_trip', store=True)
    profit_per_trip_p = fields.Float(string='กำไร% (บาท/รอบ)')

    # ========== METHODS ==========

    @api.onchange('delivery_type')
    def _onchange_delivery_type(self):
        """
        สลับค่า pickup_location และ destination เมื่อเปลี่ยนประเภทการจัดส่ง
        - เลือก 'branch' (จัดส่งมายังสาขา) → สลับต้นทาง/ปลายทาง
        - เลือก 'customer' (จัดส่งไปยังลูกค้า) → สลับกลับ
        """
        if self.pickup_location or self.destination:
            # เก็บค่าเดิมไว้ก่อน
            old_pickup = self.pickup_location
            old_destination = self.destination

            # สลับค่า
            self.pickup_location = old_destination
            self.destination = old_pickup

            delivery_type_text = 'จัดส่งมายังสาขา' if self.delivery_type == 'branch' else 'จัดส่งไปยังลูกค้า'
            _logger.info(f"🔄 [SWAP] Swapped locations for {delivery_type_text}:")
            _logger.info(f"    pickup_location: {old_pickup} → {self.pickup_location}")
            _logger.info(f"    destination: {old_destination} → {self.destination}")

    def write(self, vals):
        """Override write เพื่อบังคับให้คำนวณ shipping_cost_raw ใหม่"""

        # ป้องกัน infinite loop: ถ้ากำลังคำนวณอยู่ ไม่ต้อง trigger ซ้อน
        if self.env.context.get('skip_recompute'):
            return super(ShipmentInformation, self).write(vals)

        _logger.info(f"=== WRITE METHOD CALLED for {self.name} ===")
        _logger.info(f"Values to write: {vals}")
        _logger.info(f"Current shipping_cost_raw: {self.shipping_cost_raw}")
        _logger.info(f"Current shipping_cost: {self.shipping_cost}")
        _logger.info(f"Current trip_allowance: {self.trip_allowance}")
        _logger.info(f"Current daily_allowance: {self.daily_allowance}")

        result = super(ShipmentInformation, self).write(vals)

        # ฟิลด์ที่ต้อง trigger การคำนวณ shipping_cost ใหม่
        fields_to_trigger = [
            'distance_km', 'vehicle_type_id', 'pickup_location', 'destination',
            'fuel_price_per_liter', 'fuel_consumption_rate',
            'vehicle', 'salvage_value', 'depreciation_period',
            'annual_vehicle_tax_y', 'annual_insurance_class2', 'annual_compulsory_insurance1',
            'labor_costs', 'working_days_per_month', 'driver_salary',
            'maintenance_cost', 'trips_per_day', 'labor_cost_per_trip',
            'other_expenses', 'profit_per_trip_p'
        ]

        # ถ้ามีการเปลี่ยนแปลงฟิลด์ใดฟิลด์หนึ่ง → คำนวณใหม่
        if any(field in vals for field in fields_to_trigger):
            _logger.info("🔄 Triggering recompute for shipping_cost fields...")

            # ใช้ context เพื่อป้องกัน infinite loop
            for record in self.with_context(skip_recompute=True):
                # Reset ค่าก่อนเสมอ
                if record.distance_km < 100:
                    record.daily_allowance = 0.0
                    _logger.info(f"🔧 [WRITE] Force reset daily_allowance to 0 (distance: {record.distance_km} km)")
                elif record.distance_km >= 100:
                    record.trip_allowance = 0.0
                    _logger.info(f"🔧 [WRITE] Force reset trip_allowance to 0 (distance: {record.distance_km} km)")

                # จากนั้นคำนวณใหม่
                record._compute_trip_allowance()
                record._compute_daily_allowance()
                record._compute_fuel_used()
                record._compute_fuel_cost()
                record._compute_vehicle_cost()
                record._compute_depreciation_per_trip()
                record._compute_annual_vehicle_tax()
                record._compute_annual_insurance_class1()
                record._compute_annual_compulsory_insurance()
                record._compute_total_depreciation_per_trip()
                record._compute_total_labor_per_trip()
                record._compute_total_cost_per_trip()
                record._compute_profit_per_trip()
                record._compute_shipping_cost()

            _logger.info(f"✅ After recompute - trip_allowance: {self.trip_allowance}")
            _logger.info(f"✅ After recompute - daily_allowance: {self.daily_allowance}")
            _logger.info(f"✅ After recompute - shipping_cost_raw: {self.shipping_cost_raw}")
            _logger.info(f"✅ After recompute - shipping_cost: {self.shipping_cost}")
        else:
            # ถ้าไม่มีการเปลี่ยนแปลงฟิลด์ที่เกี่ยวข้อง ก็ยังต้องตรวจสอบและแก้ไขค่าที่ผิด
            _logger.info("🔍 Checking allowances for inconsistencies...")
            for record in self.with_context(skip_recompute=True):
                should_update = False

                # ตรวจสอบว่าค่าเบี้ยเลี้ยงและค่าเที่ยวถูกต้องหรือไม่
                if record.distance_km and record.vehicle_type_id:
                    # กรณีระยะทาง < 100 กม. ต้องไม่มีค่าเบี้ยเลี้ยง
                    if record.distance_km < 100 and record.daily_allowance != 0.0:
                        _logger.warning(f"⚠️ Found incorrect daily_allowance: {record.daily_allowance} (should be 0)")
                        record.daily_allowance = 0.0
                        should_update = True

                    # กรณีระยะทาง >= 100 กม. ต้องไม่มีค่าเที่ยว
                    if record.distance_km >= 100 and record.trip_allowance != 0.0:
                        _logger.warning(f"⚠️ Found incorrect trip_allowance: {record.trip_allowance} (should be 0)")
                        record.trip_allowance = 0.0
                        should_update = True

                    # กรณีระยะทาง < 100 กม. ต้องมีค่าเที่ยวตามประเภทรถ
                    if record.distance_km < 100:
                        vehicle_name = record.vehicle_type_id.name or ''
                        expected_trip = 0.0

                        if '4 ล้อ' in vehicle_name:
                            expected_trip = 45.0
                        elif '6 ล้อ' in vehicle_name:
                            expected_trip = 60.0
                        elif '10 ล้อ' in vehicle_name:
                            expected_trip = 75.0

                        if record.trip_allowance != expected_trip:
                            _logger.warning(
                                f"⚠️ Found incorrect trip_allowance: {record.trip_allowance} (should be {expected_trip})")
                            record.trip_allowance = expected_trip
                            should_update = True

                    # กรณีระยะทาง >= 100 กม. ต้องมีค่าเบี้ยเลี้ยง
                    if record.distance_km >= 100 and record.daily_allowance != 210.0:
                        _logger.warning(f"⚠️ Found incorrect daily_allowance: {record.daily_allowance} (should be 210)")
                        record.daily_allowance = 210.0
                        should_update = True

                if should_update:
                    _logger.info("✅ Fixed allowances inconsistencies")

        _logger.info(f"Final - trip_allowance: {self.trip_allowance}")
        _logger.info(f"Final - daily_allowance: {self.daily_allowance}")
        _logger.info(f"Final - shipping_cost_raw: {self.shipping_cost_raw}")
        _logger.info(f"Final - shipping_cost: {self.shipping_cost}")
        _logger.info("=" * 50)

        return result

    @api.onchange('vehicle_type_id')
    def _onchange_vehicle_type_id_profit(self):
        """ดึงค่า profit_per_trip_p เริ่มต้นจาก shipping.cost"""
        if self.vehicle_type_id and self.vehicle_type_id.profit_per_trip_p:
            self.profit_per_trip_p = self.vehicle_type_id.profit_per_trip_p

        # บังคับคำนวณค่าเที่ยวและค่าเบี้ยเลี้ยงใหม่
        if self.distance_km:
            _logger.info(f"🔄 [ONCHANGE] Recalculating allowances for distance: {self.distance_km} km")
            self._compute_trip_allowance()
            self._compute_daily_allowance()

    @api.onchange('profit_per_trip_p')
    def _onchange_profit_per_trip_p(self):
        """อัพเดทการคำนวณเมื่อแก้ไข profit_per_trip_p"""
        if self.profit_per_trip_p and self.total_cost_per_trip:
            # คำนวณ profit ใหม่
            self.profit_per_trip = self.total_cost_per_trip * (self.profit_per_trip_p / 100)
            # คำนวณ shipping cost ใหม่
            self.shipping_cost_raw = self.total_cost_per_trip + self.profit_per_trip

            # ปัดเศษ
            if self.shipping_cost_raw > 0:
                remainder = self.shipping_cost_raw % 100
                if remainder >= 50:
                    self.shipping_cost = math.ceil(self.shipping_cost_raw / 100) * 100
                else:
                    self.shipping_cost = math.floor(self.shipping_cost_raw / 100) * 100

    @api.depends('pickup_location', 'destination')
    def _compute_distance(self):
        """ คำนวณระยะทางโดยใช้ Google Routes API """
        for order in self:
            if order.pickup_location and order.destination:
                try:
                    google_api_key = "AIzaSyCHKkMOyDdI29v52SULcRx_OcB3i-MD7lw"
                    url = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
                    headers = {
                        "Content-Type": "application/json",
                        "X-Goog-Api-Key": google_api_key,
                        "X-Goog-FieldMask": "originIndex,destinationIndex,distanceMeters,duration"
                    }
                    payload = {
                        "origins": [{"waypoint": {"address": order.pickup_location}}],
                        "destinations": [{"waypoint": {"address": order.destination}}],
                        "travelMode": "DRIVE"
                    }

                    response = requests.post(url, headers=headers, json=payload)
                    data = response.json()

                    _logger.info(f"Google Routes API Response: {data}")

                    if response.status_code == 200 and data:
                        if "distanceMeters" in data[0]:
                            order.distance_km = data[0]["distanceMeters"] / 1000
                            # บังคับคำนวณค่าเบี้ยเลี้ยงและค่าเที่ยวใหม่ทันทีหลังได้ระยะทาง
                            order._compute_trip_allowance()
                            order._compute_daily_allowance()
                        else:
                            _logger.error("❌ No valid distance found in API response")
                            order.distance_km = 0.0
                    else:
                        order.distance_km = 0.0
                        _logger.error(f"Google API Error: {data}")

                except Exception as e:
                    order.distance_km = 0.0
                    _logger.error(f"Google Routes API Error: {e}")

    @api.depends('vehicle_type_id', 'distance_km')
    def _compute_trip_allowance(self):
        """
        คำนวณค่าเที่ยวตามประเภทรถ:
        - รถ 4 ล้อ: 45 บาท
        - รถ 6 ล้อ / 6 ล้อเฮี๊ยบ: 60 บาท
        - รถ 10 ล้อ: 75 บาท
        - ใช้เฉพาะเมื่อระยะทาง < 100 กม. เท่านั้น
        """
        for record in self:
            # Reset ค่าเป็น 0 ก่อนเสมอ
            record.trip_allowance = 0.0

            if not record.vehicle_type_id or not record.distance_km:
                _logger.info(f"⚠️ [TRIP_ALLOWANCE] No vehicle or distance - set to 0")
                continue

            # ถ้าระยะทางมากกว่าหรือเท่ากับ 100 กม. ไม่ได้ค่าเที่ยว
            if record.distance_km >= 100:
                _logger.info(f"❌ [TRIP_ALLOWANCE] ระยะทาง {record.distance_km} กม. >= 100 กม. - ไม่ได้ค่าเที่ยว")
                continue

            vehicle_name = record.vehicle_type_id.name or ''

            if '4 ล้อ' in vehicle_name:
                record.trip_allowance = 45.0
                _logger.info(f"✅ [TRIP_ALLOWANCE] รถ 4 ล้อ - ค่าเที่ยว 45 บาท (ระยะทาง {record.distance_km} กม.)")
            elif '6 ล้อ' in vehicle_name:
                record.trip_allowance = 60.0
                _logger.info(f"✅ [TRIP_ALLOWANCE] รถ 6 ล้อ - ค่าเที่ยว 60 บาท (ระยะทาง {record.distance_km} กม.)")
            elif '10 ล้อ' in vehicle_name:
                record.trip_allowance = 75.0
                _logger.info(f"✅ [TRIP_ALLOWANCE] รถ 10 ล้อ - ค่าเที่ยว 75 บาท (ระยะทาง {record.distance_km} กม.)")
            else:
                _logger.warning(f"⚠️ [TRIP_ALLOWANCE] ไม่พบประเภทรถที่ตรงกัน: {vehicle_name}")

    @api.depends('distance_km')
    def _compute_daily_allowance(self):
        """
        คำนวณค่าเบี้ยเลี้ยง:
        - ใช้เฉพาะเมื่อระยะทาง >= 100 กม. = 210 บาท
        - ถ้าระยะทาง < 100 กม. = 0 บาท
        """
        for record in self:
            # Reset ค่าเป็น 0 ก่อนเสมอ
            record.daily_allowance = 0.0

            _logger.info(f"🔍 [DAILY_ALLOWANCE] Checking distance: {record.distance_km} กม.")

            # บังคับ reset ค่าก่อนเสมอ
            if not record.distance_km or record.distance_km == 0:
                _logger.info(f"⚠️ [DAILY_ALLOWANCE] No distance - set to 0")
            elif record.distance_km >= 100:
                record.daily_allowance = 210.0
                _logger.info(
                    f"✅ [DAILY_ALLOWANCE] ระยะทาง {record.distance_km} กม. >= 100 กม. - ได้ค่าเบี้ยเลี้ยง 210 บาท")
            else:
                _logger.info(
                    f"❌ [DAILY_ALLOWANCE] ระยะทาง {record.distance_km} กม. < 100 กม. - ไม่ได้ค่าเบี้ยเลี้ยง (SET TO 0)")

    @api.depends('distance_km', 'fuel_consumption_rate')
    def _compute_fuel_used(self):
        """คำนวณ: distance_km * 2 / fuel_consumption_rate = fuel_used_per_trip"""
        for record in self:
            if record.fuel_consumption_rate:
                record.fuel_used_per_trip = (record.distance_km * 2) / record.fuel_consumption_rate
            else:
                record.fuel_used_per_trip = 0.0

    @api.depends('fuel_used_per_trip', 'fuel_price_per_liter')
    def _compute_fuel_cost(self):
        """คำนวณ: fuel_used_per_trip * fuel_price_per_liter = fuel_cost_per_trip"""
        for record in self:
            record.fuel_cost_per_trip = record.fuel_used_per_trip * record.fuel_price_per_liter

    @api.depends('vehicle')
    def _compute_vehicle_cost(self):
        """คำนวณ: vehicle * 12/100/12/30/4 = vehicle_cost"""
        for record in self:
            if record.vehicle:
                record.vehicle_cost = record.vehicle * 12 / 100 / 12 / 30 / 4
            else:
                record.vehicle_cost = 0.0

    @api.depends('vehicle_cost', 'vehicle', 'salvage_value', 'depreciation_period')
    def _compute_depreciation_per_trip(self):
        """คำนวณ: vehicle_cost + ((vehicle - salvage_value)/5/12/30/4) = depreciation_per_trip"""
        for record in self:
            if record.vehicle and record.salvage_value:
                period = record.depreciation_period if record.depreciation_period else 5
                depreciation_part = (record.vehicle - record.salvage_value) / period / 12 / 30 / 4
                record.depreciation_per_trip = record.vehicle_cost + depreciation_part
            else:
                record.depreciation_per_trip = record.vehicle_cost

    @api.depends('annual_vehicle_tax_y')
    def _compute_annual_vehicle_tax(self):
        """คำนวณ: annual_vehicle_tax_y/12/30 = annual_vehicle_tax"""
        for record in self:
            if record.annual_vehicle_tax_y:
                record.annual_vehicle_tax = record.annual_vehicle_tax_y / 12 / 30
            else:
                record.annual_vehicle_tax = 0.0

    @api.depends('annual_insurance_class2')
    def _compute_annual_insurance_class1(self):
        """คำนวณ: annual_insurance_class2/365 = annual_insurance_class1"""
        for record in self:
            if record.annual_insurance_class2:
                record.annual_insurance_class1 = record.annual_insurance_class2 / 365
            else:
                record.annual_insurance_class1 = 0.0

    @api.depends('annual_compulsory_insurance1')
    def _compute_annual_compulsory_insurance(self):
        """คำนวณ: annual_compulsory_insurance1/365 = annual_compulsory_insurance"""
        for record in self:
            if record.annual_compulsory_insurance1:
                record.annual_compulsory_insurance = record.annual_compulsory_insurance1 / 365
            else:
                record.annual_compulsory_insurance = 0.0

    @api.depends('labor_cost_per_trip', 'maintenance_cost', 'distance_km', 'other_expenses')
    def _compute_total_labor_per_trip(self):
        """คำนวณ: labor_cost_per_trip + (maintenance_cost * distance_km * 2) + other_expenses = total_labor_per_trip"""
        for record in self:
            maintenance_expense = record.maintenance_cost * record.distance_km * 2
            record.total_labor_per_trip = (
                    record.labor_cost_per_trip +
                    maintenance_expense +
                    record.other_expenses
            )

    @api.depends('depreciation_per_trip', 'annual_vehicle_tax', 'annual_insurance_class1',
                 'annual_compulsory_insurance')
    def _compute_total_depreciation_per_trip(self):
        """คำนวณ: SUM(depreciation_per_trip:annual_compulsory_insurance)/4 = total_depreciation_per_trip"""
        for record in self:
            total = (
                    record.depreciation_per_trip +
                    record.annual_vehicle_tax +
                    record.annual_insurance_class1 +
                    record.annual_compulsory_insurance
            )
            record.total_depreciation_per_trip = total / 4

    @api.depends('fuel_cost_per_trip', 'total_depreciation_per_trip', 'total_labor_per_trip')
    def _compute_total_cost_per_trip(self):
        """ คำนวณราคาต้นทุนรวมต่อรอบ """
        for record in self:
            record.total_cost_per_trip = (
                    record.fuel_cost_per_trip +
                    record.total_depreciation_per_trip +
                    record.total_labor_per_trip
            )

    @api.depends('total_cost_per_trip', 'profit_per_trip_p')
    def _compute_profit_per_trip(self):
        """คำนวณ: total_cost_per_trip * (profit_per_trip_p/100) = profit_per_trip"""
        for record in self:
            if record.profit_per_trip_p:
                record.profit_per_trip = record.total_cost_per_trip * (record.profit_per_trip_p / 100)
            else:
                record.profit_per_trip = 0.0

    @api.depends('distance_km', 'vehicle_type_id',
                 'fuel_cost_per_trip', 'total_depreciation_per_trip', 'total_labor_per_trip',
                 'total_cost_per_trip', 'profit_per_trip', 'profit_per_trip_p')
    def _compute_shipping_cost(self):
        """คำนวณค่าขนส่งตามระยะทางและประเภทรถ"""
        for record in self:
            _logger.info(f"=== Computing shipping_cost for Sale Order {record.name} ===")
            _logger.info(f"distance_km: {record.distance_km}")
            _logger.info(f"vehicle_type_id: {record.vehicle_type_id}")
            _logger.info(f"total_cost_per_trip: {record.total_cost_per_trip}")
            _logger.info(f"profit_per_trip: {record.profit_per_trip}")
            _logger.info(f"profit_per_trip_p: {record.profit_per_trip_p}")

            has_rate_per_km = hasattr(record.vehicle_type_id, 'rate_per_km') and record.vehicle_type_id.rate_per_km
            _logger.info(f"has_rate_per_km: {has_rate_per_km}")
            if has_rate_per_km:
                _logger.info(f"rate_per_km: {record.vehicle_type_id.rate_per_km}")

            if not record.distance_km or not record.vehicle_type_id:
                record.shipping_cost_raw = 0.0
                record.shipping_cost = 0.0
                _logger.warning(f"Missing distance_km or vehicle_type_id - setting to 0")
                continue

            if has_rate_per_km:
                record.shipping_cost_raw = record.distance_km * record.vehicle_type_id.rate_per_km
                _logger.info(f"Using rate_per_km calculation: {record.shipping_cost_raw}")
            else:
                total_cost = record.total_cost_per_trip or 0.0
                profit = record.profit_per_trip or 0.0
                record.shipping_cost_raw = total_cost + profit
                _logger.info(f"Using cost+profit calculation: {total_cost} + {profit} = {record.shipping_cost_raw}")

            if record.shipping_cost_raw > 0:
                remainder = record.shipping_cost_raw % 100
                if remainder >= 50:
                    record.shipping_cost = math.ceil(record.shipping_cost_raw / 100) * 100
                else:
                    record.shipping_cost = math.floor(record.shipping_cost_raw / 100) * 100
                _logger.info(f"Rounded shipping_cost: {record.shipping_cost} (remainder: {remainder})")
            else:
                record.shipping_cost = 0.0
                _logger.warning(f"shipping_cost_raw is 0 or negative!")

            _logger.info(f"Final: shipping_cost_raw={record.shipping_cost_raw}, shipping_cost={record.shipping_cost}")
            _logger.info("=" * 50)

    def action_fix_allowances(self):
        """
        ปุ่มสำหรับแก้ไขค่าเบี้ยเลี้ยงและค่าเที่ยวที่ผิดพลาด
        ใช้เมื่อค่าที่คำนวณไม่ตรงกับเงื่อนไข
        """
        for record in self:
            _logger.info(f"🔧 [FIX] Fixing allowances for SO: {record.name}")
            _logger.info(f"    Distance: {record.distance_km} km")
            _logger.info(f"    Old trip_allowance: {record.trip_allowance}")
            _logger.info(f"    Old daily_allowance: {record.daily_allowance}")

            # บังคับคำนวณใหม่ทั้งหมด
            record._compute_trip_allowance()
            record._compute_daily_allowance()
            record._compute_total_labor_per_trip()
            record._compute_total_cost_per_trip()
            record._compute_profit_per_trip()
            record._compute_shipping_cost()

            _logger.info(f"    New trip_allowance: {record.trip_allowance}")
            _logger.info(f"    New daily_allowance: {record.daily_allowance}")
            _logger.info(f"    New total_cost_per_trip: {record.total_cost_per_trip}")
            _logger.info(f"✅ [FIX] Fixed successfully!")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'สำเร็จ',
                'message': 'คำนวณค่าเบี้ยเลี้ยงและค่าเที่ยวใหม่เรียบร้อยแล้ว',
                'type': 'success',
                'sticky': False,
            }
        }