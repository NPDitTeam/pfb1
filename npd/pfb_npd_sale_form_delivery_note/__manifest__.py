{
    'name': 'PFB NPD Sale Form Delivery Note',
    'version': '14.0.o',
    'summary': 'ใบส่งมอบสินค้า',
    'description': "",
    'author': 'Devtest',
    # pfb_npd_sale_form_rent_invoice          -> get_total_baht_text, confirmed_time ฯลฯ
    # npd_rental_equipment_contract_qweb      -> rental_contract_full (วางฟิลด์เลขที่ใบส่งมอบต่อท้าย)
    'depends': [
        'base',
        'sale',
        'pfb_npd_sale_form_rent_invoice',
        'npd_rental_equipment_contract_qweb',
    ],
    'data': [
        "data/ir_sequence.xml",
        "views/sale_order_view.xml",
        "report/pfb_npd_sale_form_delivery_note.xml"
    ],

}
